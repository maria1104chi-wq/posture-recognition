"""
FastAPI API服务
提供视频流处理、WebSocket推送、RESTful API接口
"""
import os
import sys
import time
import asyncio
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime
import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import load_config, SystemConfig, BehaviorType, AlertLevel
from src.detector import YOLODetector, DetectionResult
from src.logic_engine import LogicEngine, BehaviorAlert
from src.utils import save_capture, image_to_base64, setup_logging, format_timestamp


class CameraStream:
    """摄像头视频流处理器"""
    
    def __init__(self, camera_id: int, rtsp_url: str, config: SystemConfig,
                 detector: YOLODetector, logic_engine: LogicEngine):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.config = config
        self.detector = detector
        self.logic_engine = logic_engine
        
        self.cap = None
        self.is_running = False
        self.current_frame = None
        self.last_detection_time = 0
        self.frame_count = 0
        self.fps = 0
        
        self.websocket_clients: List[WebSocket] = []
        
        self._lock = threading.Lock()
    
    def start(self):
        """启动视频流捕获"""
        self.is_running = True
        threading.Thread(target=self._capture_loop, daemon=True).start()
        logger.info(f"Camera {self.camera_id} stream started")
    
    def stop(self):
        """停止视频流捕获"""
        self.is_running = False
        if self.cap is not None:
            self.cap.release()
        logger.info(f"Camera {self.camera_id} stream stopped")
    
    def _capture_loop(self):
        """视频流捕获循环"""
        try:
            self.cap = cv2.VideoCapture(self.rtsp_url)
            
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera {self.camera_id}: {self.rtsp_url}")
                return
            
            last_frame_time = time.time()
            
            while self.is_running:
                ret, frame = self.cap.read()
                
                if not ret or frame is None:
                    logger.warning(f"Camera {self.camera_id}: Failed to read frame, reconnecting...")
                    time.sleep(1)
                    self.cap.release()
                    self.cap = cv2.VideoCapture(self.rtsp_url)
                    continue
                
                with self._lock:
                    self.current_frame = frame.copy()
                
                self.frame_count += 1
                
                # 计算FPS
                current_time = time.time()
                elapsed = current_time - last_frame_time
                if elapsed > 0:
                    self.fps = 1.0 / elapsed
                last_frame_time = current_time
                
                # 控制帧率
                sleep_time = (1.0 / self.config.max_fps) - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except Exception as e:
            logger.error(f"Camera {self.camera_id} capture error: {e}")
        finally:
            if self.cap is not None:
                self.cap.release()
    
    def process_frame(self) -> Optional[Dict[str, Any]]:
        """处理当前帧并返回结果"""
        with self._lock:
            if self.current_frame is None:
                return None
            frame = self.current_frame.copy()
        
        current_time = time.time()
        
        # 按间隔进行推理
        if current_time - self.last_detection_time < (1.0 / self.config.max_fps) * self.config.inference_interval:
            return {"frame": frame, "detections": [], "alerts": []}
        
        # 执行检测
        detections = self.detector.detect(frame)
        
        # 处理行为逻辑
        alerts = self.logic_engine.process_detections(self.camera_id, detections, current_time)
        
        # 绘制检测结果
        output_frame = self.detector.draw_detections(frame, detections)
        
        # 保存告警抓图
        for alert in alerts:
            capture_path = save_capture(
                output_frame, 
                self.camera_id, 
                alert.behavior,
                self.config.capture_dir
            )
            alert.capture_path = capture_path
        
        self.last_detection_time = current_time
        
        return {
            "frame": output_frame,
            "detections": [d.to_dict() for d in detections],
            "alerts": [a.to_dict() for a in alerts]
        }
    
    async def add_client(self, websocket: WebSocket):
        """添加WebSocket客户端"""
        await websocket.accept()
        self.websocket_clients.append(websocket)
        logger.info(f"Client connected to camera {self.camera_id}, total clients: {len(self.websocket_clients)}")
    
    def remove_client(self, websocket: WebSocket):
        """移除WebSocket客户端"""
        if websocket in self.websocket_clients:
            self.websocket_clients.remove(websocket)
            logger.info(f"Client disconnected from camera {self.camera_id}, total clients: {len(self.websocket_clients)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有客户端"""
        disconnected = []
        
        for client in self.websocket_clients:
            try:
                await client.send_json(message)
            except Exception:
                disconnected.append(client)
        
        # 清理断开的连接
        for client in disconnected:
            self.remove_client(client)


class APIServer:
    """API服务器"""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.app = FastAPI(title="塑料造粒工厂监控系统", version="1.0.0")
        
        # 配置CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # 初始化组件
        self.detector = YOLODetector(config)
        self.detector.initialize()
        
        self.logic_engine = LogicEngine(config)
        
        # 初始化摄像头流
        self.camera_streams: Dict[int, CameraStream] = {}
        for camera in config.cameras:
            if camera.enabled:
                stream = CameraStream(
                    camera.id,
                    camera.rtsp_url,
                    config,
                    self.detector,
                    self.logic_engine
                )
                self.camera_streams[camera.id] = stream
                stream.start()
        
        # 设置路由
        self._setup_routes()
        
        # 启动后台任务
        self.cleanup_task = None
    
    def _setup_routes(self):
        """设置API路由"""
        
        @self.app.get("/")
        async def root():
            return {"message": "塑料造粒工厂监控系统API", "version": "1.0.0"}
        
        @self.app.get("/api/cameras")
        async def get_cameras():
            """获取摄像头列表"""
            cameras = []
            for cam_id, stream in self.camera_streams.items():
                cameras.append({
                    "id": cam_id,
                    "name": next((c.name for c in self.config.cameras if c.id == cam_id), f"Camera {cam_id}"),
                    "line_number": next((c.line_number for c in self.config.cameras if c.id == cam_id), 0),
                    "fps": stream.fps,
                    "frame_count": stream.frame_count,
                    "client_count": len(stream.websocket_clients)
                })
            return {"cameras": cameras}
        
        @self.app.get("/api/cameras/{camera_id}/status")
        async def get_camera_status(camera_id: int):
            """获取摄像头状态"""
            if camera_id not in self.camera_streams:
                raise HTTPException(status_code=404, detail="Camera not found")
            
            status = self.logic_engine.get_camera_status(camera_id)
            status["fps"] = self.camera_streams[camera_id].fps
            status["frame_count"] = self.camera_streams[camera_id].frame_count
            
            return status
        
        @self.app.get("/api/alerts")
        async def get_alerts(limit: int = 50):
            """获取告警记录"""
            alerts = self.logic_engine.get_recent_alerts(limit)
            return {"alerts": alerts, "total": len(alerts)}
        
        @self.app.post("/api/snapshot/{camera_id}")
        async def take_snapshot(camera_id: int):
            """手动抓拍"""
            if camera_id not in self.camera_streams:
                raise HTTPException(status_code=404, detail="Camera not found")
            
            stream = self.camera_streams[camera_id]
            with stream._lock:
                if stream.current_frame is None:
                    raise HTTPException(status_code=503, detail="No frame available")
                
                frame = stream.current_frame.copy()
            
            capture_path = save_capture(frame, camera_id, "manual", self.config.capture_dir)
            return {"capture_path": capture_path, "timestamp": format_timestamp()}
        
        @self.app.websocket("/ws/{camera_id}")
        async def websocket_endpoint(websocket: WebSocket, camera_id: int):
            """WebSocket视频流推送"""
            if camera_id not in self.camera_streams:
                await websocket.close(code=4004, reason="Camera not found")
                return
            
            stream = self.camera_streams[camera_id]
            await stream.add_client(websocket)
            
            try:
                while True:
                    # 等待接收消息 (保持连接)
                    try:
                        data = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                    except asyncio.TimeoutError:
                        pass
                    
                    # 处理帧并推送
                    result = stream.process_frame()
                    if result and result["frame"] is not None:
                        frame_b64 = image_to_base64(result["frame"])
                        
                        message = {
                            "camera_id": camera_id,
                            "timestamp": time.time(),
                            "frame": frame_b64,
                            "detections": result["detections"],
                            "alerts": result["alerts"]
                        }
                        
                        await stream.broadcast(message)
                    
                    await asyncio.sleep(0.05)  # 20 FPS max for WebSocket
                    
            except WebSocketDisconnect:
                stream.remove_client(websocket)
            except Exception as e:
                logger.error(f"WebSocket error for camera {camera_id}: {e}")
                stream.remove_client(websocket)
        
        @self.app.on_event("startup")
        async def startup_event():
            logger.info("API server started")
        
        @self.app.on_event("shutdown")
        async def shutdown_event():
            logger.info("Shutting down API server")
            for stream in self.camera_streams.values():
                stream.stop()
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """运行服务器"""
        uvicorn.run(self.app, host=host, port=port)


def main():
    """主函数"""
    # 加载配置
    config = load_config()
    
    # 设置日志
    setup_logging(config.log_dir)
    
    # 确保目录存在
    os.makedirs(config.capture_dir, exist_ok=True)
    os.makedirs(config.log_dir, exist_ok=True)
    
    # 创建并运行服务器
    server = APIServer(config)
    server.run(host=config.api_host, port=config.api_port)


if __name__ == "__main__":
    main()
