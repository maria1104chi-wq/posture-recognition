"""
行为逻辑判断引擎
基于检测结果和时间序列分析，识别工人的各种行为和状态
"""
import time
from typing import Dict, List, Optional, Any
from collections import deque, defaultdict
from dataclasses import dataclass, field
from loguru import logger

from .config import (
    SystemConfig, BehaviorType, AlertLevel, 
    BEHAVIOR_ALERT_LEVELS, CameraConfig
)
from .detector import DetectionResult
from .utils import point_in_polygon, get_box_center, calculate_distance, format_timestamp


@dataclass
class PersonState:
    """人员状态跟踪类"""
    track_id: int
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    position_history: deque = field(default_factory=lambda: deque(maxlen=60))
    current_behavior: str = BehaviorType.NORMAL
    behavior_start_time: float = field(default_factory=time.time)
    alert_triggered: bool = False
    
    def update_position(self, bbox: List[int], timestamp: float):
        """更新位置信息"""
        self.position_history.append({
            "bbox": bbox,
            "center": get_box_center(bbox),
            "timestamp": timestamp
        })
        self.last_seen = timestamp
    
    def get_movement_distance(self, window_seconds: float = 5.0) -> float:
        """计算指定时间窗口内的移动距离"""
        if len(self.position_history) < 2:
            return 0.0
        
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        
        positions = [p for p in self.position_history if p["timestamp"] >= cutoff_time]
        
        if len(positions) < 2:
            return 0.0
        
        total_distance = 0.0
        for i in range(1, len(positions)):
            dist = calculate_distance(
                positions[i-1]["center"],
                positions[i]["center"]
            )
            total_distance += dist
        
        return total_distance
    
    def is_stationary(self, threshold_pixels: float = 50.0, window_seconds: float = 10.0) -> bool:
        """判断是否静止"""
        return self.get_movement_distance(window_seconds) < threshold_pixels


@dataclass
class BehaviorAlert:
    """行为告警类"""
    camera_id: int
    camera_name: str
    line_number: int
    behavior: str
    person_track_id: int
    level: str
    timestamp: float
    description: str
    capture_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "line_number": self.line_number,
            "behavior": self.behavior,
            "person_track_id": self.person_track_id,
            "level": self.level,
            "timestamp": self.timestamp,
            "formatted_time": format_timestamp(self.timestamp),
            "description": self.description,
            "capture_path": self.capture_path
        }


class LogicEngine:
    """行为逻辑判断引擎"""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.sedentary_threshold = config.sedentary_threshold
        self.sleep_threshold = config.sleep_threshold
        
        # 每个摄像头的人员状态跟踪
        # camera_id -> track_id -> PersonState
        self.person_states: Dict[int, Dict[int, PersonState]] = defaultdict(dict)
        
        # 告警历史
        self.alert_history: List[BehaviorAlert] = []
        self.max_alert_history = 1000
        
        # ROI区域定义 (从配置中获取)
        self.camera_rois: Dict[int, Dict[str, List[List[int]]]] = {}
        for camera in config.cameras:
            self.camera_rois[camera.id] = camera.roi_zones
        
        logger.info("Logic engine initialized")
    
    def process_detections(self, camera_id: int, detections: List[DetectionResult], 
                          frame_timestamp: float) -> List[BehaviorAlert]:
        """处理检测结果，识别行为并生成告警"""
        alerts = []
        
        # 获取或创建摄像头的人员状态字典
        if camera_id not in self.person_states:
            self.person_states[camera_id] = {}
        
        # 更新现有人员状态
        active_track_ids = set()
        
        for det in detections:
            if det.class_name == "person" and det.track_id is not None:
                track_id = det.track_id
                active_track_ids.add(track_id)
                
                # 更新或创建人员状态
                if track_id not in self.person_states[camera_id]:
                    self.person_states[camera_id][track_id] = PersonState(track_id=track_id)
                
                person = self.person_states[camera_id][track_id]
                person.update_position(det.bbox, frame_timestamp)
                
                # 识别行为
                behavior = self._identify_behavior(camera_id, person, detections)
                
                # 检查是否需要告警
                alert = self._check_alert(camera_id, person, behavior)
                if alert:
                    alerts.append(alert)
        
        # 清理消失的人员
        disappeared_tracks = set(self.person_states[camera_id].keys()) - active_track_ids
        for track_id in disappeared_tracks:
            logger.debug(f"Person track {track_id} disappeared from camera {camera_id}")
            # 可以选择保留一段时间的历史记录
        
        return alerts
    
    def _identify_behavior(self, camera_id: int, person: PersonState, 
                          all_detections: List[DetectionResult]) -> str:
        """识别人员当前行为"""
        if len(person.position_history) < 2:
            return BehaviorType.NORMAL
        
        last_position = person.position_history[-1]
        center = last_position["center"]
        
        # 获取ROI区域
        rois = self.camera_rois.get(camera_id, {})
        
        # 查找附近的其他检测对象
        nearby_objects = self._find_nearby_objects(center, all_detections, person.track_id)
        
        # 行为识别逻辑
        behavior = BehaviorType.NORMAL
        
        # 1. 检查是否在控制面板区域 -> 开机/停机动作
        if "control_panel" in rois and point_in_polygon(
            [int(center[0]), int(center[1])], rois["control_panel"]
        ):
            if "hand" in nearby_objects or any(d.class_name == "hand" for d in all_detections):
                behavior = BehaviorType.POWER_ON
        
        # 2. 检查是否有塑料长条 -> 抽拉塑料长条
        if "plastic_strip" in nearby_objects:
            behavior = BehaviorType.PULL_PLASTIC
        
        # 3. 检查是否在颗粒区域 -> 检查塑料颗粒
        if "granules" in nearby_objects:
            behavior = BehaviorType.CHECK_GRANULES
        
        # 4. 检查是否在称重区域且有电子秤 -> 称重打包
        if ("weighing_area" in rois and point_in_polygon(
            [int(center[0]), int(center[1])], rois["weighing_area"]
        )) and "scale" in nearby_objects:
            behavior = BehaviorType.WEIGH_PACK
        
        # 5. 检查是否在机头区域且有工具 -> 清理机头
        if ("machine_head" in rois and point_in_polygon(
            [int(center[0]), int(center[1])], rois["machine_head"]
        )) and "tool" in nearby_objects:
            behavior = BehaviorType.CLEAN_MACHINE_HEAD
        
        # 6. 检查是否在真空设备区域 -> 检查清理真空设备
        if ("vacuum_device" in rois and point_in_polygon(
            [int(center[0]), int(center[1])], rois["vacuum_device"]
        )):
            behavior = BehaviorType.CLEAN_VACUUM
        
        # 7. 检查是否久坐或睡眠 (基于静止时间)
        if person.is_stationary(threshold_pixels=30.0, window_seconds=10.0):
            stationary_duration = time.time() - person.behavior_start_time
            
            if stationary_duration > self.sleep_threshold:
                behavior = BehaviorType.SLEEP
            elif stationary_duration > self.sedentary_threshold:
                behavior = BehaviorType.SEDENTARY
        
        # 更新行为状态
        if behavior != person.current_behavior:
            person.current_behavior = behavior
            person.behavior_start_time = time.time()
            person.alert_triggered = False
            logger.info(f"Camera {camera_id}, Track {person.track_id}: Behavior changed to {behavior}")
        
        return behavior
    
    def _find_nearby_objects(self, center: List[float], detections: List[DetectionResult],
                            exclude_track_id: int, max_distance: float = 150.0) -> List[str]:
        """查找中心点附近的物体"""
        nearby = []
        
        for det in detections:
            if det.track_id == exclude_track_id:
                continue
            
            dist = calculate_distance(center, det.center)
            if dist < max_distance:
                nearby.append(det.class_name)
        
        return nearby
    
    def _check_alert(self, camera_id: int, person: PersonState, 
                    behavior: str) -> Optional[BehaviorAlert]:
        """检查是否需要生成告警"""
        # 获取摄像头信息
        camera_info = next(
            (c for c in self.config.cameras if c.id == camera_id), 
            None
        )
        
        if camera_info is None:
            return None
        
        # 检查告警级别
        alert_level = BEHAVIOR_ALERT_LEVELS.get(behavior, AlertLevel.INFO)
        
        # 只对WARNING和CRITICAL级别生成告警，且避免重复告警
        if alert_level in [AlertLevel.WARNING, AlertLevel.CRITICAL]:
            if not person.alert_triggered:
                person.alert_triggered = True
                
                description = self._generate_alert_description(behavior, person)
                
                alert = BehaviorAlert(
                    camera_id=camera_id,
                    camera_name=camera_info.name,
                    line_number=camera_info.line_number,
                    behavior=behavior,
                    person_track_id=person.track_id,
                    level=alert_level,
                    timestamp=time.time(),
                    description=description
                )
                
                self.alert_history.append(alert)
                
                # 限制历史记录大小
                if len(self.alert_history) > self.max_alert_history:
                    self.alert_history = self.alert_history[-self.max_alert_history:]
                
                logger.warning(f"Alert generated: {description}")
                return alert
        
        return None
    
    def _generate_alert_description(self, behavior: str, person: PersonState) -> str:
        """生成告警描述"""
        duration = time.time() - person.behavior_start_time
        
        descriptions = {
            BehaviorType.SEDENTARY: f"工人久坐已达{duration:.0f}秒",
            BehaviorType.SLEEP: f"工人疑似睡眠已达{duration:.0f}秒，请立即处理！",
        }
        
        return descriptions.get(behavior, f"检测到{behavior}")
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近的告警记录"""
        recent = self.alert_history[-limit:]
        return [alert.to_dict() for alert in reversed(recent)]
    
    def get_camera_status(self, camera_id: int) -> Dict[str, Any]:
        """获取摄像头状态"""
        if camera_id not in self.person_states:
            return {"active_persons": 0, "persons": []}
        
        persons = []
        for track_id, person in self.person_states[camera_id].items():
            persons.append({
                "track_id": track_id,
                "current_behavior": person.current_behavior,
                "duration": time.time() - person.behavior_start_time,
                "last_seen": format_timestamp(person.last_seen)
            })
        
        return {
            "active_persons": len(persons),
            "persons": persons
        }
