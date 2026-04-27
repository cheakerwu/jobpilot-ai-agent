"""
工具函数
"""
import os
import yaml
import json
import logging
from datetime import datetime


def setup_logger(name='job_agent', log_dir='logs', level=logging.INFO):
    """设置日志系统"""
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)

    # 日志文件路径
    log_file = os.path.join(log_dir, f'job_agent_{datetime.now():%Y%m%d}.log')

    # 创建logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 文件handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)

    # 控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # 格式化
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 添加handler
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def load_config(config_path='config/config.yaml'):
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_user_profile(profile_path='config/user_profile.json'):
    """加载用户配置"""
    with open(profile_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_job_info(job, show_detail=False):
    """格式化岗位信息"""
    info = f"[{job.id}] {job.title} - {job.company}\n"
    info += f"    城市: {job.city} | 薪资: {job.salary} | 状态: {job.status}"

    if job.match_score:
        info += f" | 匹配度: {job.match_score}%"

    if show_detail:
        info += f"\n    链接: {job.url}"
        if job.description:
            info += f"\n    描述: {job.description[:100]}..."

    return info
