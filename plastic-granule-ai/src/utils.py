"""
工具函数模块
"""
import os
import time
import base64
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List
from PIL import Image
import numpy as np
import cv2
from loguru import logger


def generate_capture_filename(camera_id: int, behavior: str) -> str:
    """生成抓图文件名"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = hashlib.md5(f"{camera_id}_{time.time()}".encode()).hexdigest()[:8]
    return f"camera_{camera_id}_{behavior}_{timestamp}_{unique_id}.jpg"


def save_capture(image: np.ndarray, camera_id: int, behavior: str, capture_dir: str = "captures") -> str:
    """保存抓图并返回文件路径"""
    os.makedirs(capture_dir, exist_ok=True)
    filename = generate_capture_filename(camera_id, behavior)
    filepath = os.path.join(capture_dir, filename)
    
    # 确保图像是BGR格式 (OpenCV默认)
    if len(image.shape) == 2 or image.shape[2] == 1:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
    
    cv2.imwrite(filepath, image)
    logger.info(f"Capture saved: {filepath}")
    return filepath


def image_to_base64(image: np.ndarray) -> str:
    """将图像转换为base64字符串"""
    # 确保图像是BGR格式
    if len(image.shape) == 2 or image.shape[2] == 1:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
    
    _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buffer).decode('utf-8')


def calculate_iou(box1: List[int], box2: List[int]) -> float:
    """计算两个边界框的IoU"""
    x1, y1, x2, y2 = box1
    x3, y3, x4, y4 = box2
    
    # 计算交集
    xi1, yi1 = max(x1, x3), max(y1, y3)
    xi2, yi2 = min(x2, x4), min(y2, y4)
    
    inter_width = max(0, xi2 - xi1)
    inter_height = max(0, yi2 - yi1)
    inter_area = inter_width * inter_height
    
    # 计算并集
    area1 = (x2 - x1) * (y2 - y1)
    area2 = (x4 - x3) * (y4 - y3)
    union_area = area1 + area2 - inter_area
    
    if union_area == 0:
        return 0.0
    
    return inter_area / union_area


def point_in_polygon(point: List[int], polygon: List[List[int]]) -> bool:
    """判断点是否在多边形内"""
    x, y = point
    inside = False
    
    n = len(polygon)
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside


def get_box_center(box: List[int]) -> List[float]:
    """获取边界框中心点"""
    x1, y1, x2, y2 = box
    return [(x1 + x2) / 2, (y1 + y2) / 2]


def calculate_distance(point1: List[float], point2: List[float]) -> float:
    """计算两点间距离"""
    return ((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2) ** 0.5


def format_timestamp(timestamp: Optional[float] = None) -> str:
    """格式化时间戳"""
    if timestamp is None:
        timestamp = time.time()
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def setup_logging(log_dir: str = "logs"):
    """配置日志"""
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"system_{datetime.now().strftime('%Y%m%d')}.log")
    
    logger.remove()
    logger.add(
        log_file,
        rotation="00:00",
        retention="7 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module} | {message}"
    )
    logger.add(
        lambda msg: print(msg, end=""),
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <cyan>{module}</cyan> | {message}"
    )
    
    return logger
