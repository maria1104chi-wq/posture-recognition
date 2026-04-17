"""
塑料造粒工厂监控系统配置文件
"""
import os
from typing import Dict, List
from pydantic import BaseModel


class CameraConfig(BaseModel):
    """摄像头配置"""
    id: int
    name: str
    rtsp_url: str
    line_number: int  # 生产线编号
    enabled: bool = True
    roi_zones: Dict[str, List[List[int]]] = {}  # 感兴趣区域


class SystemConfig(BaseModel):
    """系统配置"""
    # 摄像头配置
    cameras: List[CameraConfig]
    
    # 模型配置
    model_path: str = "models/best.pt"
    model_confidence: float = 0.5
    model_iou: float = 0.45
    input_size: tuple = (640, 480)
    
    # 推理配置
    inference_interval: int = 5  # 每5帧推理一次
    max_fps: int = 15
    
    # 行为识别阈值
    sedentary_threshold: int = 300  # 秒，久坐判定时间
    sleep_threshold: int = 600  # 秒，睡眠判定时间
    
    # 存储配置
    capture_dir: str = "captures"
    log_dir: str = "logs"
    
    # API配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    ws_heartbeat_interval: int = 30
    
    # GPU配置
    use_gpu: bool = True
    gpu_id: int = 0


# 默认摄像头配置 (8条生产线)
DEFAULT_CAMERAS = [
    CameraConfig(
        id=i,
        name=f"生产线{i+1}号摄像头",
        rtsp_url=os.getenv(f"CAMERA_{i}_RTSP", f"rtsp://admin:password@192.168.1.{10+i}:554/stream1"),
        line_number=i+1,
        enabled=True,
        roi_zones={
            "control_panel": [[100, 100], [200, 100], [200, 200], [100, 200]],
            "machine_head": [[300, 150], [450, 150], [450, 300], [300, 300]],
            "weighing_area": [[500, 200], [600, 200], [600, 350], [500, 350]],
            "vacuum_device": [[50, 250], [150, 250], [150, 400], [50, 400]],
        }
    )
    for i in range(8)
]


def load_config() -> SystemConfig:
    """加载系统配置"""
    return SystemConfig(
        cameras=DEFAULT_CAMERAS,
        model_path=os.getenv("MODEL_PATH", "models/best.pt"),
        model_confidence=float(os.getenv("MODEL_CONFIDENCE", "0.5")),
        model_iou=float(os.getenv("MODEL_IOU", "0.45")),
        inference_interval=int(os.getenv("INFERENCE_INTERVAL", "5")),
        max_fps=int(os.getenv("MAX_FPS", "15")),
        sedentary_threshold=int(os.getenv("SEDENTARY_THRESHOLD", "300")),
        sleep_threshold=int(os.getenv("SLEEP_THRESHOLD", "600")),
        capture_dir=os.getenv("CAPTURE_DIR", "captures"),
        log_dir=os.getenv("LOG_DIR", "logs"),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "8000")),
        use_gpu=os.getenv("USE_GPU", "true").lower() == "true",
        gpu_id=int(os.getenv("GPU_ID", "0")),
    )


# 行为类型定义
class BehaviorType:
    SEDENTARY = "久坐"
    SLEEP = "睡眠"
    POWER_ON = "开机动作"
    PULL_PLASTIC = "抽拉塑料长条"
    CHECK_GRANULES = "检查塑料颗粒"
    WEIGH_PACK = "称重打包"
    POWER_OFF = "停机动作"
    CLEAN_MACHINE_HEAD = "清理机头"
    CLEAN_VACUUM = "检查清理真空设备"
    NORMAL = "正常"


# 告警级别
class AlertLevel:
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


BEHAVIOR_ALERT_LEVELS = {
    BehaviorType.SEDENTARY: AlertLevel.WARNING,
    BehaviorType.SLEEP: AlertLevel.CRITICAL,
    BehaviorType.POWER_ON: AlertLevel.INFO,
    BehaviorType.PULL_PLASTIC: AlertLevel.INFO,
    BehaviorType.CHECK_GRANULES: AlertLevel.INFO,
    BehaviorType.WEIGH_PACK: AlertLevel.INFO,
    BehaviorType.POWER_OFF: AlertLevel.INFO,
    BehaviorType.CLEAN_MACHINE_HEAD: AlertLevel.INFO,
    BehaviorType.CLEAN_VACUUM: AlertLevel.INFO,
    BehaviorType.NORMAL: AlertLevel.INFO,
}
