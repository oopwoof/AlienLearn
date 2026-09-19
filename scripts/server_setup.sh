#!/usr/bin/env bash
# AlienLearn 内测部署：一次性准备。
#
# 已在干净的 ubuntu:22.04 容器里跑通（Python 3.10、服务真的起来了、/api/meta 返回 200、
# 重复执行不覆盖已填好的 .env）。**仍未在真机验证**：容器验不了真实的
# 网络、防火墙、安全组，也验不了 systemd 真正把服务拉起来并在重启后自愈。
# 第一次部署时请逐段读、逐段跑，出错就停下来看，不要盲目重跑。
#
# 用法（Ubuntu 22.04）：
#     bash scripts/server_setup.sh
# root 直接跑，或普通用户带 sudo 跑，都可以。
#
# 幂等：重复执行不会破坏已有部署（不会覆盖 .env，不会重复 clone）。

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/alienlearn}"
REPO="${REPO:-https://github.com/oopwoof/AlienLearn.git}"
SERVICE_NAME="alienlearn"
# 服务以专用系统用户身份运行，不是 root。见下面 5/5 那段的说明。
APP_USER="${APP_USER:-alienlearn}"

# 国内轻量服务器默认就是 root 登录，而最小镜像里往往连 sudo 都没有 ——
# 写死 sudo 会让脚本在第一行就 127 退出。这里按当前身份选择提权方式。
if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
elif command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
else
  echo "需要 root 权限，但当前既不是 root 也没有 sudo。请用 root 登录后重跑。" >&2
  exit 1
fi

say() { printf '\n\033[1m▸ %s\033[0m\n' "$1"; }

say "1/6 系统依赖"
$SUDO apt update
$SUDO apt install -y python3-venv git sqlite3

say "2/6 服务账号"
if id -u "$APP_USER" >/dev/null 2>&1; then
  echo "$APP_USER 已存在"
else
  $SUDO useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
  echo "已创建系统用户 $APP_USER（不能登录，只用来跑服务）"
fi

say "3/6 代码"
if [ -d "$APP_DIR/.git" ]; then
  echo "已存在，改为更新：$APP_DIR"
  # 仓库归 $APP_USER 所有，而这里是 root 在操作 —— 不声明 safe.directory
  # 的话 git 会以"dubious ownership"拒绝，升级时才会撞上。
  $SUDO git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
  $SUDO git -C "$APP_DIR" pull --ff-only
else
  $SUDO git clone "$REPO" "$APP_DIR"
fi

say "4/6 虚拟环境"
cd "$APP_DIR"
[ -d .venv ] || $SUDO python3 -m venv .venv
$SUDO .venv/bin/pip install --upgrade pip
$SUDO .venv/bin/pip install -r requirements.txt

say "5/6 .env 与数据目录"
if [ -f .env ]; then
  echo ".env 已存在，保持不动（不覆盖已填好的 key）"
else
  $SUDO tee .env >/dev/null <<'ENVEOF'
MOCK_LLM=0
LLM_API_KEY=填这里

# 成本保险丝，见 backend/limits.py。用尽后返回 503 拒绝，刻意不降级到规则桩
DAILY_TURN_BUDGET=2000
TURNS_PER_MIN_PLAYER=20
TURNS_PER_MIN_IP=40

# 注意：HOST/PORT 只对 `python backend/run.py` 生效。systemd 直接调 uvicorn，
# 监听地址写在 scripts/alienlearn.service 的 ExecStart 里 —— 要改端口改那里。
ENVEOF
  echo "已生成 .env 模板 —— 现在去填 LLM_API_KEY，填完再继续"
fi

# 埋点库的目录。让服务自己首次写入时创建的话，属主会跟着当时的身份走，
# 换用户跑就写不进去了 —— 这里显式建好并交给 $APP_USER。
$SUDO mkdir -p "$APP_DIR/data"
$SUDO chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
$SUDO chmod 600 "$APP_DIR/.env"     # 别让同机其他用户读到 key

say "6/6 systemd"
# 服务不跑在 root 下：这是个对公网开放的 web 服务，被打穿时的爆炸半径
# 不该是整台机器。unit 里写死 User=alienlearn，与上面的属主对齐。
$SUDO cp "$APP_DIR/scripts/${SERVICE_NAME}.service" "/etc/systemd/system/${SERVICE_NAME}.service"
$SUDO systemctl daemon-reload
$SUDO systemctl enable "$SERVICE_NAME"
echo "装好了。填完 .env 后："
echo "    ${SUDO:+sudo }systemctl restart $SERVICE_NAME"
echo "    ${SUDO:+sudo }systemctl status  $SERVICE_NAME"
echo "    ${SUDO:+sudo }journalctl -u $SERVICE_NAME -f"
echo
echo "然后按 docs/deploy.md 的「上线前必须验的三件」逐条验，不要跳。"
