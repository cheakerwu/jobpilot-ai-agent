"""
FastAPI 启动脚本
"""
import uvicorn
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

if __name__ == "__main__":
    uvicorn.run(
        "web_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        loop="asyncio"  # 使用 asyncio 事件循环
    )
