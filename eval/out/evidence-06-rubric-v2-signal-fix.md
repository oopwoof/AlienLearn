# 第六轮：档位判定进代码（rubric v2）+ 一个从第一天就坏着的信号链路

日期：2026-08-20 · 链路：live / deepseek-chat · trace：`ramen_en__*__live__0820-*.json`

## 这一轮做了什么

上一轮的结论是「散文 rubric + few-shot 的标定能力到顶了，要换手段」。这一轮把两个手段都落了：

1. **档位判定从 prompt 挪进代码**（rubric v2-typed）。Pedagogy 只做抽取——
   每个问题给 span / fix / type / note，severity 由 `config.SEVERITY_BY_TYPE`
   的映射表决定。和「数值不给 LLM 碰」同一个原则：现在档位错了能一眼分清
   是抽取错（span/type 不对）还是映射错（表定错了档）。
   白名单 type（缩略/近义/正式度/标点/大小写/所有格）在代码层直接丢弃，
   模型想挑刺也挑不进 HUD。
2. **56 条独立标注集 `labeled_v2`**，第一次给 span 建了 ground truth——
   span 是唯一进玩家视野的诊断产物（原句高亮直接用它），此前它的准确性从未被度量。
   出题按 error type 分类学网格（每 type × 3-4 个非拉面语境，先句后标），
   `check_leakage()` 机器自检保证样本不在任何 Agent prompt 里，
   `check_labels()` 保证标注档位永远由 type 推导、和线上口径同一张表。

## 数字（rubric v2 口径，与 evidence-01~04 不可比）

| 集合 | 样本 | 档位准确率 | 备注 |
| --- | --- | --- | --- |
| 核心集 dev（normal/broken/jailbreak） | 30 | **96.7%** | 从 v1 的「保送 100%」回落，预期内 |
| 泛化集 boundary（留出，未动过一字） | 10 | **60.0%** | 与 v1 的 60-70% 区间持平；今天两次重跑一致 |
| **labeled_v2（独立，56 条）** | 56 | **92.9%** | span 召回 **93.0%** · span 精确率 **95.2%** · type 准确率 **95.0%** |

**两次完整重跑 labeled_v2，六个指标逐位一致。** 上一轮 10 条集合重跑波动 10 个百分点，
56 条集合波动为 0——「扩样本的首要目的是让数字稳到能做决策」这个假设本身也被验证了。

失误第一次可归因到层：boundary 的 4 个失误里 3 个是抽取层假阳性
（最集中的一类是「陈述语序提问」：You have any beer? 被报 aux_missing——
labeled_v2 里同类陷阱 2/56 中招，量化了它的发生率）；1 个是映射层的
边界争议（存在句 there is + 复数）。修哪一层、值不值得修，现在有数可依。

过程中靠 dev 集错例归因新增了一个类型：`copula_omission`（省略 be，minor）
从 `be_mismatch`（用错 be，major）里拆出来——「This soup very much delicious」
是口音式零系动词，母语者照常接话；「I is hungry」才扎耳。这是 taxonomy
的修正，不是照分数改标：30 条人工标注仍然一条没动。

## 顺手发现的大 bug：live 局的任务推进从第一天起就基本不工作

翻历史 trace 时发现：live 模式下 deepseek-chat 演完台词经常不输出
`<<<SIGNAL>>>` 信号行——三份历史 normal trace 里 advance 只有 1/10、1/10、0/10，
emotion 几乎全是默认值。也就是说 **live 局的玩家会永远卡在第一幕直到能量耗尽**。
之前没发现，因为评测只看 Router/Pedagogy 的分数，而完整对局演示走的是 mock。

修法双保险：当前轮消息末尾加格式提醒（历史不留痕）+ marker 缺失时走一次
小型非流式「信号提取」兜底（读的是 NPC 实际说的话，revealed_secret 反而更准）。
信号一律带 `source` 字段（marker/extractor/mock/default）——降级可见，
trace 里能直接量服从率（本轮实测 marker 1/5 + extractor 4/5）。

修复后 live 整局实测：花店场景 8 轮四幕全推进、未解锁时正确岔开、
被认真追问才松口、第 8 轮通关。

## 教训

- **评测只覆盖单轮指标时，跨轮的状态机链路就是盲区。** Router/Pedagogy
  的分数再漂亮，也测不出「任务永远不推进」这种要玩完整局才暴露的断裂。
  下一步的评测欠账：把「一局能不能在 N 轮内正常通关」变成可跑的套件。
- 样本量就是决策资格：波动 10 个点的指标不配指导 prompt 改动，
  56 条 + 两次重跑逐位一致之后，92.9% 这个数字才第一次「能用」。
