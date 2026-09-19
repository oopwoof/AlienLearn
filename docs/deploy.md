# 内测部署

目标很窄：**让 5-10 个熟人能打开链接玩，并且把埋点稳稳存下来。**
不是做高可用，不是做公开发布 —— 那些等内测有结论再说。

## 为什么选国内轻量服务器

| 方案 | 结论 |
| --- | --- |
| **腾讯云 / 阿里云轻量应用服务器**（推荐） | 内测对象基本都在国内，访问稳定。几十元/月，自带持久磁盘 |
| Vercel / Netlify | **不能用。** 文件系统是临时的，一次 redeploy 埋点就归零 —— 而收数据是内测的全部目的 |
| Railway / Render / Fly | 能跑，但国内访问不稳定。测试者连不上就等于没数据 |

DeepSeek 也在国内，所以服务端到模型这一跳同样受益。

## 一次性准备

最低配置够用（1 核 2G）。系统选 Ubuntu 22.04。

```bash
git clone https://github.com/oopwoof/AlienLearn.git /tmp/al && bash /tmp/al/scripts/server_setup.sh
```

`scripts/server_setup.sh` 把下面这一节的步骤（依赖 / 服务账号 / clone / venv /
.env 模板 / 数据目录 / systemd）串成一遍，幂等，重复跑不会覆盖已填好的 `.env`。
root 直接跑或普通用户带 sudo 跑都可以。

### 已经验过什么，没验过什么

2026-09-19 在干净的 `ubuntu:22.04` 容器里跑通了这些（**不是真机**）：

| 验过的 | 结果 |
| --- | --- |
| 全新机器、root 登录、**没有 sudo** | 跑到底，退出码 0 |
| Python 3.10（本机开发是 3.12） | venv、依赖、`import main` 全 OK |
| `systemd-analyze verify` unit 语法 | 通过 |
| `systemctl start` + `is-enabled` | active / enabled |
| 服务跑在谁名下 | `alienlearn`，不是 root |
| 非 root 身份写埋点库 | `data/telemetry.db` 属主 alienlearn，建局 200 |
| `kill -9` 之后 `Restart=always` | 6 秒内自愈，仍是非 root |
| 重复执行（升级路径） | `git pull --ff-only`，已填的 key 原样保留 |

> ⚠ **仍然没在真机上跑过。** 容器验不了这些：真实网络与 DNS、安全组/防火墙
> 放行 8000、公网 IP 从外面打得开、机器重启后服务自己回来、国内访问 GitHub
> 和 DeepSeek 的实际速度。第一次部署仍请逐段读、逐段看输出，出错就停。

容器里撞出来两个真问题，都已修：**脚本原来写死 `sudo`**，而国内轻量服务器默认
root 登录、最小镜像里没有 sudo —— 第一行就 `command not found` 退出 127；
**unit 原来没有 `User=`**，服务会以 root 身份对公网提供服务，
脚本前面辛苦做的 chown 和 `chmod 600` 全部白做。

手工做也一样（脚本里就是这些）：

```bash
sudo apt update && sudo apt install -y python3-venv git sqlite3
git clone https://github.com/oopwoof/AlienLearn.git /opt/alienlearn
cd /opt/alienlearn
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

`.env`（**不要提交，key 只存在服务器上**）：

```env
MOCK_LLM=0
LLM_API_KEY=sk-...

# 注意：HOST/PORT 只对 `python backend/run.py` 生效。systemd 直接调 uvicorn，
# 监听地址写死在 scripts/alienlearn.service 的 ExecStart 里 —— 要改端口改那里，
# 改这里不会有任何效果。
HOST=0.0.0.0
PORT=8000

DAILY_TURN_BUDGET=2000    # 成本保险丝，见 backend/limits.py
TURNS_PER_MIN_PLAYER=20
TURNS_PER_MIN_IP=40
```

```bash
chmod 600 .env        # 别让同机其他用户读到 key
```

## 用 systemd 托管

自己 `nohup` 起进程的话，机器一重启服务就没了，而你不会立刻发现。

unit 文件就在仓库里：`scripts/alienlearn.service`（`server_setup.sh` 会替你拷到
`/etc/systemd/system/`）。想把埋点库和代码分开存，把里面 `ALIENLEARN_DATA_DIR`
那行的注释去掉。

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now alienlearn
sudo systemctl status alienlearn          # 起没起来看这里
sudo journalctl -u alienlearn -f          # 看日志
```

安全组 / 防火墙放通 8000。

## 上线前必须验的三件

**1. 埋点真的持久化**（这一项不过，整个内测白做）

```bash
curl -s localhost:8000/api/metrics | head -c 200
sudo systemctl restart alienlearn
sqlite3 /opt/alienlearn/data/telemetry.db "SELECT COUNT(*) FROM events;"
```

重启前后行数必须一致。

**2. 闸门生效**

临时把 `DAILY_TURN_BUDGET=1` 重启，发一轮应该返回 **503**（世界观内的文案）；
连发几轮触发 **429**。验完改回去。

**3. 外网能开**

用手机流量（不是同一个 WiFi）打开 `http://<公网IP>:8000`，走完开场三屏并说一句话。

## 每天看一眼

```bash
.venv/bin/python scripts/daily_report.py
```

一屏输出：按自然日的局数 / 玩家数 / 胜率 / ★北极星（词/局）/ 轮次 / turn 额度水位 /
反馈条数与均星，外加 A/B 两臂对比和次日留存。样本不足 5 时它会自己说"先别下结论" ——
内测头几天最容易犯的错就是对着 3 个人的数据调产品。

结尾那行自查很重要：如果库里出现了 `e2e_`/`smoke_`/`live_`/`diag_` 开头的会话，
说明埋点写入闸（`game_state.channel_for`）失效了，指标已经开始被自测流量污染。

**备份埋点。** 数据是这轮唯一的产出：

```bash
sqlite3 data/telemetry.db ".backup /opt/backup-$(date +%F).db"
```

（`scripts/purge_telemetry.py` 是清历史残渣用的，内测期间正常不需要跑。它默认只预演，
`--execute` 前会自动整库备份。）

## 关于 HTTPS 和隐私

内测走 http 可以接受（`localStorage` 在 http 下正常工作）。公开发之前要上 TLS ——
届时用 caddy 或 nginx + certbot，需要一个域名。

**不收集任何个人信息**：`player_id` 是浏览器本地生成的匿名 UUID，没有账号、没有密码、
不问邮箱。它唯一的用途是把同一个人的多局串起来算留存。测试者清掉浏览器数据就等于退出。
告诉他们这一点 —— 这是应该说清的事。

## 更新

```bash
cd /opt/alienlearn && git pull
.venv/bin/pip install -r requirements.txt
sudo systemctl restart alienlearn
```

`data/` 不在版本控制里，所以 `git pull` 不会动埋点。
