#!/bin/bash
# AutoDL 换机一键接管：改隧道指向 + 更新杂具小栈配置 + 验证全链路
# 用法（在阿里云服务器上执行）：
#   bash /opt/oral-practice/scripts/autodl_switch.sh <主机> <端口> <实例ID>
# 示例：
#   bash /opt/oral-practice/scripts/autodl_switch.sh connect.bjb1.seetacloud.com 20170 8bd74a939f-150bfcd7
set -e

HOST=${1:?用法: autodl_switch.sh <主机> <端口> <实例ID>}
PORT=${2:?缺少端口}
UUID=${3:-}

echo "== 1/5 改 comfy-tunnel 指向 $HOST:$PORT"
sed -i "s|-p [0-9]* root@[a-z0-9.]*\.seetacloud\.com|-p $PORT root@$HOST|" /etc/systemd/system/comfy-tunnel.service
systemctl daemon-reload
systemctl restart comfy-tunnel
sleep 5
systemctl is-active comfy-tunnel

echo "== 2/5 更新 .env"
sed -i "s|AUTODL_SSH_TARGET=.*|AUTODL_SSH_TARGET=-p $PORT root@$HOST|" /opt/oral-practice/.env
[ -n "$UUID" ] && sed -i "s|AUTODL_INSTANCE=.*|AUTODL_INSTANCE=$UUID|" /opt/oral-practice/.env

echo "== 3/5 等 ComfyUI 上线（新实例自启约1分钟，最多等3分钟）"
ok=0
for i in $(seq 1 18); do
  code=$(curl -s -m10 -o /dev/null -w "%{http_code}" http://127.0.0.1:6006/system_stats || echo 000)
  [ "$code" = "200" ] && { ok=1; break; }
  sleep 10
done
[ "$ok" = "1" ] && echo "ComfyUI 已上线" || { echo "⚠️ ComfyUI 未上线，请到实例终端跑: bash /root/start_comfy.sh"; }

echo "== 4/5 重建 mischub-video 容器使环境变量生效"
cd /opt/oral-practice && docker compose up -d mischub-video > /dev/null 2>&1
sleep 5

echo "== 5/5 全链路验证"
docker exec mischub-video ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=8 -p $PORT root@$HOST 'echo SSH_LINK_OK' || echo "⚠️ 容器→实例 ssh 不通"
curl -s -m10 http://127.0.0.1:6006/object_info/WanVideoModelLoader -o /dev/null -w "Wan节点: %{http_code}\n" || true
curl -s -m10 -o /dev/null -w "杂具小栈: %{http_code}\n" http://localhost:8503/video/healthz
echo "完成 ✅"
