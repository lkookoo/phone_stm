#!/bin/bash
# deploy/deploy.sh - X1.0 Market Monitor 部署脚本
# 用法：在 Oracle 服务器上执行
#   chmod +x deploy.sh && ./deploy.sh

set -e

echo "======================================"
echo " X1.0 Market Monitor - 部署"
echo "======================================"

# 1. 系统更新
echo "[1/5] 更新系统包..."
sudo apt-get update -qq && sudo apt-get upgrade -y -qq

# 2. 安装 Docker + Compose
if ! command -v docker &> /dev/null; then
    echo "[2/5] 安装 Docker..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
    echo "  Docker 安装完成，请重新登录后继续"
else
    echo "[2/5] Docker 已安装，跳过"
fi

# 3. 防火墙（Oracle 内部 iptables）
echo "[3/5] 配置 iptables..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || true

# 4. 构建并启动
echo "[4/5] 构建镜像..."
cd "$(dirname "$0")/.."
docker compose build

echo "[5/5] 启动服务..."
docker compose up -d

echo ""
echo "======================================"
echo " ✅ 部署完成"
echo "======================================"
echo ""
docker compose ps
echo ""
echo "访问地址："
echo "  http://$(curl -s ifconfig.me)"
echo ""
echo "查看日志：docker compose logs -f backend"
echo "重启服务：docker compose restart"
echo "停止服务：docker compose down"