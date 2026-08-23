#!/usr/bin/env bash
# AlienLearn 内测部署：一次性准备。
#
# ⚠ 未在真机验证过 —— 服务器还没买。写在这里是为了把 docs/deploy.md 的
#   人工步骤固化成可复核的顺序，不是为了"跑一下就完事"。第一次部署时
#   请逐段读、逐段跑，出错就停下来看，不要盲目重跑。
#
# 用法（Ubuntu 22.04，普通用户执行，需要 sudo 权限）：
#     bash scripts/server_setup.sh
#
# 幂等：重复执行不会破坏已有部署（不会覆盖 .env，不会重复 clone）。

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/alienlearn}"
REPO="${REPO:-https://github.com/oopwoof/AlienLearn.git}"
SERVICE_NAME="alienlearn"

say() { printf '\n\033[1m▸ %s\033[0m\n' "$1"; }

say "1/5 系统依赖"
sudo apt update
sudo apt install -y python3-venv git sqlite3

say "2/5 代码"
if [ -d "$APP_DIR/.git" ]; then
  echo "已存在，改为更新：$APP_DIR"
  sudo git -C "$APP_DIR" pull --ff-only
else
  sudo git clone "$REPO" "$APP_DIR"
  sudo chown -R "$USER":"$USER" "$APP_DIR"
fi

say "3/5 虚拟环境"
cd "$APP_DIR"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

say "4/5 .env"
if [ -f .env ]; then
  echo ".env 已存在，保持不动（不覆盖已填好的 key）"
else
  cat > .env <<'ENVEOF'
MOCK_LLM=0
LLM_API_KEY=填这里

# 关键：127.0.0.1 只能本机访问，外面打不开
HOST=0.0.0.0
PORT=8000

# 成本保险丝，见 backend/limits.py。用尽后返回 503 拒绝，刻意不降级到规则桩
DAILY_TURN_BUDGET=2000
TURNS_PER_MIN_PLAYER=20
TURNS_PER_MIN_IP=40
ENVEOF
  echo "已生成 .env 模板 —— 现在去填 LLM_API_KEY，填完再继续"
fi
chmod 600 .env        # 别让同机其他用户读到 key

say "5/5 systemd"
sudo cp "$APP_DIR/scripts/${SERVICE_NAME}.service" "/etc/systemd/system/${SERVICE_NAME}.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
echo "装好了。填完 .env 后："
echo "    sudo systemctl restart $SERVICE_NAME"
echo "    sudo systemctl status  $SERVICE_NAME"
echo "    sudo journalctl -u $SERVICE_NAME -f"
echo
echo "然后按 docs/deploy.md 的「上线前必须验的三件」逐条验，不要跳。"
