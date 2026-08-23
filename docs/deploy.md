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

`scripts/server_setup.sh` 把下面这一节的步骤（依赖 / clone / venv / .env 模板 /
systemd）串成一遍，幂等，重复跑不会覆盖已填好的 `.env`。

> ⚠ **这个脚本没在真机上跑过** —— 服务器还没买。它是把人工步骤固化成可复核的
> 顺序，不是"跑一下就完事"。第一次部署请逐段读、逐段看输出，出错就停。

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

HOST=0.0.0.0          # 关键：127.0.0.1 只能本机访问，外面打不开
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
