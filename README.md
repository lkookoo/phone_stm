---
title: X1.0 Market Monitor
emoji: 📈
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# X1.0 Market Monitor

个人多市场缠论盯市系统。BTC / ETH / SOL / S&P500 / Nasdaq-100。

只盯市，不交易。

## 说明

- 后端：FastAPI + 缠论引擎
- 前端：Vue 3 + Lightweight Charts
- 数据源：Binance / OKX / Coinbase / Kraken / Yahoo Finance
- 免费实例 48 小时无活动会休眠，冷启动 ~30 秒
- 免费层无持久化，重启后 K 线会重新加载

## 免责

结构评分不代表未来收益率或交易成功概率。