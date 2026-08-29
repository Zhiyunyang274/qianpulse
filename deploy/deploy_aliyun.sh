#!/usr/bin/env bash
# 黔脉 · 云服务器部署清单
# 用法：SERVER=root@<你的服务器IP> DOMAIN=<你的域名> ./deploy_aliyun.sh
# 前置：DNS 已加 A 记录 <你的域名> -> <你的服务器IP>
set -euo pipefail

SERVER="${SERVER:?请通过环境变量 SERVER 指定，例如 root@1.2.3.4}"
DOMAIN="${DOMAIN:-qianpulse.example.com}"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR=/opt/qianpulse

echo "== 1. 上传代码（rsync，排除本地虚拟环境与缓存）"
rsync -az --delete \
  --exclude .venv --exclude __pycache__ --exclude .git \
  --exclude "*.pyc" --exclude .DS_Store --exclude node_modules \
  "$LOCAL_DIR/" "$SERVER:$REMOTE_DIR/"

echo "== 2. 服务器端：依赖与常驻服务"
ssh "$SERVER" bash -s <<'REMOTE'
set -euo pipefail
cd /opt/qianpulse

# 系统依赖（幂等）
apt-get update -qq
apt-get install -y -qq python3-venv nginx certbot python3-certbot-nginx >/dev/null

# venv + 依赖（幂等：已存在则跳过创建）
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

# 目录属主（systemd 以 www-data 运行；Streamlit 缓存写 ~/.cache）
mkdir -p /var/cache/qianpulse
chown -R www-data:www-data /opt/qianpulse /var/cache/qianpulse
# Streamlit 需要可写的 HOME 放缓存
Environment_HOME=/var/cache/qianpulse

# swap 兜底（2G 内存机器，幂等）
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# systemd 服务
cp deploy/qianpulse.service /etc/systemd/system/qianpulse.service
# 注入缓存 HOME（覆盖 deploy 模板缺省）
mkdir -p /etc/systemd/system/qianpulse.service.d
cat > /etc/systemd/system/qianpulse.service.d/cache.conf <<'OVR'
[Service]
Environment=HOME=/var/cache/qianpulse
OVR
systemctl daemon-reload
systemctl enable qianpulse >/dev/null 2>&1
systemctl restart qianpulse

# Nginx 反代（先 HTTP，certbot 再自动升级 HTTPS）
cp deploy/nginx_qianpulse.conf /etc/nginx/sites-available/qianpulse
ln -sf /etc/nginx/sites-available/qianpulse /etc/nginx/sites-enabled/qianpulse
nginx -t && systemctl reload nginx

echo "== 服务状态"
systemctl --no-pager -l status qianpulse | head -5
sleep 3
curl -s -o /dev/null -w "local 8501: %{http_code}\n" http://127.0.0.1:8501/ || true
REMOTE

echo "== 3. HTTPS（DNS 生效后执行）"
ssh "$SERVER" "certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m \${CERTBOT_EMAIL:?请设置 CERTBOT_EMAIL 环境变量} --redirect || echo 'certbot 未执行：确认 DNS 已生效后重跑此段'"

echo "== 完成"
