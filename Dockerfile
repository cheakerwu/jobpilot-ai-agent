FROM python:3.13-slim-bookworm

WORKDIR /app

# 系统依赖（weasyprint 需要）+ 阿里云镜像加速
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# 数据和配置通过 volume 挂载，不打入镜像
VOLUME ["/app/data", "/app/config", "/app/logs"]

EXPOSE 8000

ENV JOBPILOT_ENV=production

CMD ["python", "run_web.py"]
