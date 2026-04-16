"""
模型训练脚本
用于训练YOLOv8/v10模型识别塑料造粒工厂中的各种对象和行为
"""
import os
import argparse
from pathlib import Path
from ultralytics import YOLO
from loguru import logger


def setup_logging(log_dir: str = "logs"):
    """设置日志"""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "training.log")
    
    logger.remove()
    logger.add(
        log_file,
        rotation="100 MB",
        retention="7 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module} | {message}"
    )
    logger.add(
        lambda msg: print(msg, end=""),
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}"
    )


def create_dataset_yaml(data_dir: str, output_path: str):
    """创建数据集配置文件"""
    train_images = os.path.join(data_dir, "images", "train")
    val_images = os.path.join(data_dir, "images", "val")
    
    yaml_content = f"""# 塑料造粒工厂数据集配置
path: {os.path.abspath(data_dir)}
train: images/train
val: images/val

# 类别定义
names:
  0: person           # 人
  1: hand             # 手
  2: plastic_strip    # 塑料长条
  3: granules         # 塑料颗粒
  4: scale            # 电子秤
  5: control_panel    # 控制面板
  6: machine_head     # 机头
  7: vacuum_device    # 真空设备
  8: tool             # 工具
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)
    
    logger.info(f"Dataset config created: {output_path}")
    return output_path


def train_model(
    data_config: str,
    epochs: int = 100,
    img_size: int = 640,
    batch_size: int = 16,
    model_name: str = "yolov8n.pt",
    device: str = "0",
    project: str = "models",
    name: str = "plastic_granule_det",
    resume: bool = False,
    pretrained: str = None
):
    """训练模型"""
    logger.info(f"Starting training with {model_name}")
    logger.info(f"Data config: {data_config}")
    logger.info(f"Epochs: {epochs}, Batch size: {batch_size}, Image size: {img_size}")
    logger.info(f"Device: {device}")
    
    # 加载模型
    if resume and os.path.exists(os.path.join(project, name, "weights", "last.pt")):
        model_path = os.path.join(project, name, "weights", "last.pt")
        logger.info(f"Resuming from {model_path}")
        model = YOLO(model_path)
    elif pretrained and os.path.exists(pretrained):
        logger.info(f"Loading pretrained model from {pretrained}")
        model = YOLO(pretrained)
    else:
        logger.info(f"Loading base model: {model_name}")
        model = YOLO(model_name)
    
    # 开始训练
    results = model.train(
        data=data_config,
        epochs=epochs,
        imgsz=img_size,
        batch=batch_size,
        device=device,
        project=project,
        name=name,
        workers=4,
        optimizer="auto",
        verbose=True,
        save=True,
        save_period=10,  # 每10个epoch保存一次
        plots=True,      # 生成训练图表
        exist_ok=True,
        amp=True,        # 混合精度训练
        patience=50,     # 早停耐心值
        seed=42,
        deterministic=True,
    )
    
    logger.info("Training completed!")
    logger.info(f"Results saved to: {os.path.join(project, name)}")
    
    # 验证模型
    logger.info("Running validation...")
    metrics = model.val()
    logger.info(f"mAP50: {metrics.box.map50:.4f}")
    logger.info(f"mAP50-95: {metrics.box.map:.4f}")
    
    return results


def export_model(model_path: str, format: str = "onnx", img_size: int = 640):
    """导出模型"""
    logger.info(f"Exporting model from {model_path} to {format}")
    
    model = YOLO(model_path)
    
    export_path = model.export(
        format=format,
        imgsz=img_size,
        dynamic=False,
        simplify=True,
    )
    
    logger.info(f"Model exported to: {export_path}")
    return export_path


def main():
    parser = argparse.ArgumentParser(description="塑料造粒工厂检测模型训练脚本")
    
    # 训练参数
    parser.add_argument("--data", type=str, default="data/dataset.yaml",
                       help="数据集配置文件路径")
    parser.add_argument("--epochs", type=int, default=100,
                       help="训练轮数")
    parser.add_argument("--img-size", type=int, default=640,
                       help="输入图像大小")
    parser.add_argument("--batch", type=int, default=16,
                       help="批次大小")
    parser.add_argument("--model", type=str, default="yolov8n.pt",
                       help="基础模型名称或路径")
    parser.add_argument("--device", type=str, default="0",
                       help="GPU设备ID (cpu 或 0,1,2...)")
    parser.add_argument("--project", type=str, default="models",
                       help="项目目录")
    parser.add_argument("--name", type=str, default="plastic_granule_det",
                       help="实验名称")
    parser.add_argument("--resume", action="store_true",
                       help="从上次中断处继续训练")
    parser.add_argument("--pretrained", type=str, default=None,
                       help="预训练模型路径")
    
    # 导出参数
    parser.add_argument("--export", action="store_true",
                       help="导出模型")
    parser.add_argument("--export-format", type=str, default="onnx",
                       choices=["onnx", "torchscript", "engine", "coreml", "openvino"],
                       help="导出格式")
    parser.add_argument("--export-path", type=str, default=None,
                       help="要导出的模型路径")
    
    # 数据集创建
    parser.add_argument("--create-dataset", action="store_true",
                       help="创建数据集配置文件")
    parser.add_argument("--data-dir", type=str, default="data",
                       help="数据目录")
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging()
    
    # 创建数据集配置
    if args.create_dataset:
        create_dataset_yaml(args.data_dir, args.data)
        return
    
    # 导出模型
    if args.export:
        if args.export_path is None:
            args.export_path = os.path.join(args.project, args.name, "weights", "best.pt")
        export_model(args.export_path, args.export_format, args.img_size)
        return
    
    # 训练模型
    train_model(
        data_config=args.data,
        epochs=args.epochs,
        img_size=args.img_size,
        batch_size=args.batch,
        model_name=args.model,
        device=args.device,
        project=args.project,
        name=args.name,
        resume=args.resume,
        pretrained=args.pretrained,
    )


if __name__ == "__main__":
    main()
