"""
JobPilot 启动脚本
支持开发/生产模式自动切换
"""
import uvicorn
import sys
import os
import signal

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def _parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="JobPilot Web Server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("JOBPILOT_PORT", "8000")))
    parser.add_argument("--host", default=os.environ.get("JOBPILOT_HOST", "0.0.0.0"))
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    is_prod = os.environ.get("JOBPILOT_ENV", "development").lower() == "production"

    # 确保数据和日志目录存在
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # 生产模式加载 .env
    if is_prod:
        from dotenv import load_dotenv
        load_dotenv()

    uvicorn.run(
        "web_api.main:app",
        host=args.host,
        port=args.port,
        reload=not is_prod,
        workers=1 if not is_prod else 2,
        loop="asyncio",
        log_level="info" if is_prod else "debug",
    )
