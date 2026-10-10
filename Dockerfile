# Dockerfile - X1.0 Market Monitor for Hugging Face Spaces
#
# HF Spaces 要求：
#   - 监听端口 7860
#   - 非 root 用户（uid=1000）
#   - 免费层无持久化存储

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

# HF Spaces 要求 uid=1000 用户
RUN useradd -m -u 1000 user

WORKDIR /app

# 依赖先装，利用 layer cache
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 拷贝应用代码
COPY --chown=user:user app/ ./app/
COPY --chown=user:user frontend/ ./frontend/
COPY --chown=user:user run.py .
COPY --chown=user:user main.py .
COPY --chown=user:user .env.hf ./.env

USER user

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/api/market/overview || exit 1

CMD ["python", "run.py", "--port", "7860"]