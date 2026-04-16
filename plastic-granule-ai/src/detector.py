"""
YOLO检测引擎模块
支持YOLOv8/v10模型，提供高效的物体检测功能
"""
import os
import time
from typing import List, Dict, Any, Optional
from collections import deque
import numpy as np
import cv2
from ultralytics import YOLO
from loguru import logger

from .config import SystemConfig, BehaviorType
from .utils import get_box_center, point_in_polygon


class DetectionResult:
    """检测结果类"""
    def __init__(self, class_id: int, class_name: str, confidence: float, 
                 bbox: List[int], track_id: Optional[int] = None):
        self.class_id = class_id
        self.class_name = class_name
        self.confidence = confidence
        self.bbox = bbox  # [x1, y1, x2, y2]
        self.track_id = track_id
        self.center = get_box_center(bbox)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "track_id": self.track_id,
            "center": self.center
        }


class YOLODetector:
    """YOLO检测器类"""
    
    # 类别映射 (根据实际训练数据调整)
    CLASS_NAMES = {
        0: "person",           # 人
        1: "hand",             # 手
        2: "plastic_strip",    # 塑料长条
        3: "granules",         # 塑料颗粒
        4: "scale",            # 电子秤
        5: "control_panel",    # 控制面板
        6: "machine_head",     # 机头
        7: "vacuum_device",    # 真空设备
        8: "tool",             # 工具
    }
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.model_path = config.model_path
        self.confidence = config.model_confidence
        self.iou = config.model_iou
        self.input_size = config.input_size
        self.use_gpu = config.use_gpu
        self.gpu_id = config.gpu_id
        
        self.model = None
        self.device = None
        self.initialized = False
        
        # 跟踪历史 (用于行为分析)
        self.track_history: Dict[int, deque] = {}  # track_id -> 位置历史
        self.max_history_length = 30  # 保留最近30帧
        
        logger.info(f"Initializing YOLO detector with model: {self.model_path}")
    
    def initialize(self):
        """初始化模型"""
        if not os.path.exists(self.model_path):
            logger.warning(f"Model file not found: {self.model_path}, using default YOLOv8n")
            self.model = YOLO('yolov8n.pt')
        else:
            self.model = YOLO(self.model_path)
        
        # 设置设备
        if self.use_gpu:
            self.device = f"cuda:{self.gpu_id}"
            logger.info(f"Using GPU: {self.device}")
        else:
            self.device = "cpu"
            logger.info("Using CPU")
        
        # 预热模型
        dummy_frame = np.zeros((self.input_size[1], self.input_size[0], 3), dtype=np.uint8)
        self.model.predict(dummy_frame, device=self.device, verbose=False)
        
        self.initialized = True
        logger.info("YOLO detector initialized successfully")
    
    def detect(self, frame: np.ndarray, use_track: bool = True) -> List[DetectionResult]:
        """执行检测"""
        if not self.initialized:
            self.initialize()
        
        # 调整图像大小
        resized_frame = cv2.resize(frame, self.input_size)
        
        # 执行推理
        if use_track:
            results = self.model.track(
                resized_frame,
                device=self.device,
                conf=self.confidence,
                iou=self.iou,
                verbose=False,
                persist=True
            )
        else:
            results = self.model.predict(
                resized_frame,
                device=self.device,
                conf=self.confidence,
                iou=self.iou,
                verbose=False
            )
        
        detections = []
        
        if results and len(results) > 0:
            result = results[0]
            
            # 处理检测结果
            boxes = result.boxes
            if boxes is not None:
                for i in range(len(boxes)):
                    box = boxes[i]
                    
                    # 获取边界框坐标
                    xyxy = box.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = map(int, xyxy)
                    
                    # 缩放到原始图像尺寸
                    scale_x = frame.shape[1] / self.input_size[0]
                    scale_y = frame.shape[0] / self.input_size[1]
                    
                    x1 = int(x1 * scale_x)
                    y1 = int(y1 * scale_y)
                    x2 = int(x2 * scale_x)
                    y2 = int(y2 * scale_y)
                    
                    # 获取类别和置信度
                    cls_id = int(box.cls[0].cpu().numpy())
                    conf = float(box.conf[0].cpu().numpy())
                    
                    # 获取track_id (如果有)
                    track_id = None
                    if hasattr(box, 'id') and box.id is not None:
                        track_id = int(box.id[0].cpu().numpy())
                    
                    # 获取类别名称
                    cls_name = self.CLASS_NAMES.get(cls_id, f"class_{cls_id}")
                    
                    detection = DetectionResult(
                        class_id=cls_id,
                        class_name=cls_name,
                        confidence=conf,
                        bbox=[x1, y1, x2, y2],
                        track_id=track_id
                    )
                    detections.append(detection)
                    
                    # 更新跟踪历史
                    if track_id is not None:
                        if track_id not in self.track_history:
                            self.track_history[track_id] = deque(maxlen=self.max_history_length)
                        self.track_history[track_id].append({
                            "bbox": [x1, y1, x2, y2],
                            "center": detection.center,
                            "timestamp": time.time(),
                            "class_name": cls_name
                        })
        
        return detections
    
    def get_track_history(self, track_id: int) -> deque:
        """获取指定track的历史记录"""
        return self.track_history.get(track_id, deque())
    
    def clear_track_history(self, track_id: int):
        """清除指定track的历史记录"""
        if track_id in self.track_history:
            del self.track_history[track_id]
    
    def cleanup_old_tracks(self, max_age_seconds: float = 30.0):
        """清理过期的跟踪记录"""
        current_time = time.time()
        expired_tracks = []
        
        for track_id, history in self.track_history.items():
            if len(history) == 0:
                expired_tracks.append(track_id)
            else:
                last_update = history[-1]["timestamp"]
                if current_time - last_update > max_age_seconds:
                    expired_tracks.append(track_id)
        
        for track_id in expired_tracks:
            self.clear_track_history(track_id)
            logger.debug(f"Cleared expired track: {track_id}")
    
    def draw_detections(self, frame: np.ndarray, detections: List[DetectionResult]) -> np.ndarray:
        """在图像上绘制检测结果"""
        output = frame.copy()
        
        colors = {
            "person": (0, 255, 0),      # 绿色
            "hand": (255, 0, 0),        # 蓝色
            "plastic_strip": (0, 255, 255),  # 黄色
            "granules": (255, 255, 0),  # 青色
            "scale": (255, 0, 255),     # 品红
            "control_panel": (0, 128, 255),  # 橙色
            "machine_head": (128, 0, 255),   # 紫色
            "vacuum_device": (0, 255, 128),  # 青绿
            "tool": (128, 128, 128),    # 灰色
        }
        
        for det in detections:
            color = colors.get(det.class_name, (255, 255, 255))
            x1, y1, x2, y2 = det.bbox
            
            # 绘制边界框
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            
            # 绘制标签
            label = f"{det.class_name}: {det.confidence:.2f}"
            if det.track_id is not None:
                label += f" (ID: {det.track_id})"
            
            cv2.putText(output, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return output
