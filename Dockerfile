# Dockerfile - X1.0 Market Monitor for Hugging Face Spaces
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libffi-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 拷贝 app（含 app/main.py）
COPY --chown=user:user app/ ./app/
# 拷贝前端
COPY --chown=user:user frontend/ ./frontend/
# 拷贝入口脚本
COPY --chown=user:user run.py .
# 拷贝 HF 环境变量
COPY --chown=user:user .env.hf ./.env

USER user

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/api/market/overview || exit 1

CMD ["python", "run.py", "--port", "7860"]