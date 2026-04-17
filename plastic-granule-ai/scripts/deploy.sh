#!/bin/bash

# 塑料造粒工厂监控系统部署脚本
set -e

echo "=========================================="
echo "塑料造粒工厂监控系统部署脚本"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置变量
PROJECT_NAME="plastic-granule-ai"
BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-8080}
MODEL_PATH=${MODEL_PATH:-./models/best.pt}

# 检查Docker
check_docker() {
    echo -e "${YELLOW}检查Docker环境...${NC}"
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: Docker未安装${NC}"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}错误: Docker Compose未安装${NC}"
        exit 1
    fi
    
    # 检查NVIDIA Container Toolkit
    if ! docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi &> /dev/null; then
        echo -e "${YELLOW}警告: NVIDIA GPU支持可能未正确配置${NC}"
    else
        echo -e "${GREEN}✓ Docker和GPU支持正常${NC}"
    fi
}

# 创建必要目录
create_directories() {
    echo -e "${YELLOW}创建必要目录...${NC}"
    mkdir -p models logs captures data
    
    # 设置权限
    chmod 755 models logs captures data
    
    echo -e "${GREEN}✓ 目录创建完成${NC}"
}

# 下载或准备模型
prepare_model() {
    echo -e "${YELLOW}准备模型文件...${NC}"
    
    if [ -f "$MODEL_PATH" ]; then
        echo -e "${GREEN}✓ 模型文件已存在: $MODEL_PATH${NC}"
    else
        echo -e "${YELLOW}模型文件不存在，使用默认YOLOv8n模型${NC}"
        echo "首次运行时会自动下载基础模型"
    fi
}

# 配置环境变量
setup_environment() {
    echo -e "${YELLOW}配置环境变量...${NC}"
    
    # 创建.env文件
    cat > .env << EOF
# 摄像头配置 (请根据实际情况修改)
CAMERA_0_RTSP=rtsp://admin:password@192.168.1.10:554/stream1
CAMERA_1_RTSP=rtsp://admin:password@192.168.1.11:554/stream1
CAMERA_2_RTSP=rtsp://admin:password@192.168.1.12:554/stream1
CAMERA_3_RTSP=rtsp://admin:password@192.168.1.13:554/stream1
CAMERA_4_RTSP=rtsp://admin:password@192.168.1.14:554/stream1
CAMERA_5_RTSP=rtsp://admin:password@192.168.1.15:554/stream1
CAMERA_6_RTSP=rtsp://admin:password@192.168.1.16:554/stream1
CAMERA_7_RTSP=rtsp://admin:password@192.168.1.17:554/stream1

# 系统配置
MODEL_PATH=/app/models/best.pt
MODEL_CONFIDENCE=0.5
MODEL_IOU=0.45
INFERENCE_INTERVAL=5
MAX_FPS=15

# 告警阈值 (秒)
SEDENTARY_THRESHOLD=300
SLEEP_THRESHOLD=600

# API配置
API_HOST=0.0.0.0
API_PORT=${BACKEND_PORT}

# GPU配置
USE_GPU=true
GPU_ID=0

# 存储配置
CAPTURE_DIR=/app/captures
LOG_DIR=/app/logs
EOF
    
    echo -e "${GREEN}✓ 环境变量配置完成${NC}"
    echo -e "${YELLOW}请编辑.env文件配置正确的摄像头RTSP地址${NC}"
}

# 构建Docker镜像
build_images() {
    echo -e "${YELLOW}构建Docker镜像...${NC}"
    
    docker-compose build
    
    echo -e "${GREEN}✓ Docker镜像构建完成${NC}"
}

# 启动服务
start_services() {
    echo -e "${YELLOW}启动服务...${NC}"
    
    docker-compose up -d
    
    echo -e "${GREEN}✓ 服务启动完成${NC}"
    echo ""
    echo -e "${GREEN}=========================================="
    echo "服务访问地址:"
    echo -e "${GREEN}后端API: http://localhost:${BACKEND_PORT}"
    echo -e "${GREEN}前端界面: http://localhost:${FRONTEND_PORT}"
    echo -e "${GREEN}==========================================${NC}"
}

# 停止服务
stop_services() {
    echo -e "${YELLOW}停止服务...${NC}"
    
    docker-compose down
    
    echo -e "${GREEN}✓ 服务已停止${NC}"
}

# 查看日志
view_logs() {
    echo -e "${YELLOW}查看日志...${NC}"
    docker-compose logs -f "$@"
}

# 重启服务
restart_services() {
    echo -e "${YELLOW}重启服务...${NC}"
    
    docker-compose restart
    
    echo -e "${GREEN}✓ 服务已重启${NC}"
}

# 清理资源
cleanup() {
    echo -e "${YELLOW}清理Docker资源...${NC}"
    
    read -p "确定要删除所有容器、卷和镜像吗？(y/N): " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        docker-compose down -v --rmi all
        echo -e "${GREEN}✓ 清理完成${NC}"
    else
        echo "取消清理"
    fi
}

# 显示帮助
show_help() {
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  deploy     部署服务 (默认)"
    echo "  start      启动服务"
    echo "  stop       停止服务"
    echo "  restart    重启服务"
    echo "  logs       查看日志"
    echo "  rebuild    重新构建并部署"
    echo "  cleanup    清理所有Docker资源"
    echo "  help       显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 deploy          # 部署服务"
    echo "  $0 logs backend    # 查看后端日志"
    echo "  $0 cleanup         # 清理资源"
}

# 主函数
main() {
    case "${1:-deploy}" in
        deploy)
            check_docker
            create_directories
            prepare_model
            setup_environment
            build_images
            start_services
            ;;
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        logs)
            shift
            view_logs "$@"
            ;;
        rebuild)
            stop_services
            build_images
            start_services
            ;;
        cleanup)
            cleanup
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo -e "${RED}未知命令: $1${NC}"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
