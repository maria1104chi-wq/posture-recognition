# 塑料造粒工厂智能监控系统

## 项目概述
本系统用于监控8条塑料造粒生产线，通过摄像头实时识别工人动作和状态，包括：
- 久坐睡眠检测
- 开机/停机动作
- 抽拉塑料长条动作
- 检查塑料颗粒动作
- 塑料颗粒称重打包动作
- 清理机头动作
- 检查清理真空设备动作

## 系统架构
- **后端**: Python + FastAPI + YOLOv8 + OpenCV
- **前端**: Vue3 + Element Plus + WebSocket
- **部署**: Docker + NVIDIA Container Toolkit

## 目录结构
```
plastic-granule-ai/
├── data/                    # 训练数据目录
├── models/                  # 模型权重目录
├── src/                     # 后端源代码
│   ├── config.py           # 系统配置
│   ├── detector.py         # YOLO检测引擎
│   ├── logic_engine.py     # 行为逻辑判断引擎
│   ├── api_server.py       # FastAPI服务
│   └── utils.py            # 工具函数
├── frontend/                # 前端项目
│   ├── src/
│   │   ├── components/     # Vue组件
│   │   ├── views/          # 页面视图
│   │   ├── stores/         # Pinia状态管理
│   │   └── utils/          # 工具函数
│   └── package.json
├── scripts/                 # 训练和部署脚本
│   ├── train.py            # 模型训练脚本
│   └── deploy.sh           # 部署脚本
├── docker/                  # Docker配置文件
│   ├── Dockerfile.backend  # 后端镜像
│   └── Dockerfile.frontend # 前端镜像
├── logs/                    # 日志目录
├── captures/                # 抓图保存目录
├── requirements.txt         # Python依赖
└── docker-compose.yml       # Docker编排
```

## 快速开始

### 环境要求
- NVIDIA GPU (推荐RTX 3060及以上)
- NVIDIA Driver >= 470
- Docker >= 20.10
- NVIDIA Container Toolkit

### 安装步骤

1. 克隆项目
```bash
git clone <repo-url>
cd plastic-granule-ai
```

2. 配置摄像头地址
编辑 `src/config.py` 中的摄像头RTSP地址

3. 启动服务
```bash
docker-compose up -d
```

4. 访问前端
打开浏览器访问 `http://localhost:8080`

## API接口

### WebSocket连接
- URL: `ws://localhost:8000/ws/{camera_id}`
- 推送内容: 视频帧( base64) + 检测结果 + 告警信息

### RESTful API
- `GET /api/cameras` - 获取摄像头列表
- `GET /api/alerts` - 获取历史告警记录
- `POST /api/snapshot` - 手动抓拍

## 行为识别逻辑

| 行为 | 识别条件 |
|------|----------|
| 久坐睡眠 | 人员检测框持续静止>5分钟 |
| 开机动作 | 手部靠近控制面板+按钮区域变化 |
| 抽拉塑料长条 | 长条状物体移动轨迹检测 |
| 检查颗粒 | 手部在颗粒容器上方停留 |
| 称重打包 | 电子秤区域有人+手部操作 |
| 停机动作 | 手部按压急停按钮 |
| 清理机头 | 人员在机头区域+手持工具 |
| 清理真空设备 | 人员在真空设备区域操作 |

## 性能指标
- 单GPU支持8路1080P@15FPS
- 推理延迟 < 100ms
- 行为识别准确率 > 85%

## 许可证
MIT License
