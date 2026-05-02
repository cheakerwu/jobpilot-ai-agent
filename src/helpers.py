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
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f'job_agent_{datetime.now():%Y%m%d}.log')

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


_DEFAULT_CONFIG = {
    "storage": {"db_path": "data/jobs.db"},
    "resume": {"provider": "qwen", "model": "qwen-plus"},
    "server": {"allowed_origins": ["*"]},
}


def load_config(config_path=None):
    """加载配置文件，支持环境变量覆盖和默认值降级"""
    if config_path is None:
        config_path = os.environ.get("JOBPILOT_CONFIG", "config/config.yaml")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if config:
                return config
    except FileNotFoundError:
        pass
    except Exception:
        pass

    return dict(_DEFAULT_CONFIG)


def load_user_profile(profile_path='config/user_profile.json'):
    """加载用户配置"""
    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"basic_info": {}, "skills": [], "experiences": [], "filter_preferences": {}}


def wrap_user_input(text: str) -> str:
    """用 XML 标签包裹用户输入，防止 LLM 提示注入"""
    return f"<user_input>\n{text}\n</user_input>"


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
