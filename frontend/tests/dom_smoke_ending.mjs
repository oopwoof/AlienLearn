/* showEnding 三形态 + runIntro 快速通道的 jsdom 冒烟：抓运行时错误和关键 DOM 断言 */
import { JSDOM } from "jsdom";

// 路径相对本文件解析：脚本收进仓库后不该再依赖某台机器的盘符
const src = (p) => new URL(`../js/${p}`, import.meta.url).href;

const dom = new JSDOM(`<!doctype html><body><div id="overlay"><div class="card" id="card"></div></div></body>`, {
  url: "http://127.0.0.1:8123/",
});
global.window = dom.window;
global.document = dom.window.document;
global.localStorage = dom.window.localStorage;
Object.defineProperty(global, "navigator", { value: dom.window.navigator, configurable: true });
global.fetch = async () => ({ ok: false, json: async () => ({}) }); // getMetrics 拿不到就显示"没有数据"
global.matchMedia = window.matchMedia = () => ({ matches: true }); // reduced-motion：typeOut 直接整段出

const { runIntro, showEnding } = await import(src("intro.js"));

const overlay = document.querySelector("#overlay");
const card = document.querySelector("#card");

const summaryBase = {
  target_words_total: 42, target_words_per_turn: 3.5, target_language_ratio: 0.9,
  corrections_shown: 2, glitch_events: 1, out_of_scope_turns: 0, turns: 12,
  duration_sec: 300, stage_index: 2, stage_reached: "闲聊", vocab_hits: 5, crash_reason: "",
};
const stages = [{ name: "进店" }, { name: "点单" }, { name: "闲聊" }, { name: "情报" }];
const stats = { sessions: 3, wins: 1, total_target_words: 87, best_words: 42, best_stage_index: 3 };

let fails = 0;
const check = (name, cond) => { if (!cond) { fails++; console.log("X  " + name); } else console.log("OK " + name); };

// —— won
showEnding(overlay, card, { status: "won", line: "拿到了。", summary: { ...summaryBase, stage_index: 3 } }, { stages, stats });
check("won: 标题", card.textContent.includes("情报到手"));
check("won: 全节点 done", card.querySelectorAll(".prog-node.done").length === 4);
check("won: 新纪录标记", card.querySelector(".record") !== null);
check("won: 累计条", card.textContent.includes("你的第 3 局"));

// —— crashed（strikes 主因）
showEnding(overlay, card, { status: "crashed", line: "崩了。", summary: { ...summaryBase, crash_reason: "strikes", target_words_total: 10 } }, { stages, stats });
check("crashed: 主因文案", card.textContent.includes("连续三次"));
check("crashed: 精简记分板 4 块", card.querySelectorAll(".score").length === 4);
check("crashed: card 类", card.className.includes("card--crashed"));

// —— drained（最后一幕 vs 中途）
showEnding(overlay, card, { status: "drained", line: "能量尽了。", summary: { ...summaryBase, stage_index: 3, target_words_total: 10 } }, { stages, stats });
check("drained: 最后一幕文案", card.textContent.includes("就差把秘密问出口"));
showEnding(overlay, card, { status: "drained", line: "能量尽了。", summary: { ...summaryBase, stage_index: 1, target_words_total: 10 } }, { stages, stats });
check("drained: 距离感", card.textContent.includes("还差 2 幕"));
check("drained: 教学钩子", card.textContent.includes("补充全息能量"));

// —— 首局玩家（stats.sessions=1）不显示累计
showEnding(overlay, card, { status: "drained", line: "x", summary: summaryBase }, { stages, stats: { ...stats, sessions: 1 } });
check("首局: 无累计条", card.querySelector(".cume") === null);

// —— 明日目标：三形态都必须有，且位置在累计与分隔线之间
const nextScene = { scene_id: "flower_en", display_name: "暮色花店", target_language_label: "英语" };
for (const status of ["won", "crashed", "drained"]) {
  showEnding(overlay, card, { status, line: "x", summary: { ...summaryBase, crash_reason: "suspicion" } },
    { stages, stats, nextScene, sessionId: "s1" });
  check(`${status}: 有明日目标块`, card.querySelector(".tomorrow") !== null);
}
showEnding(overlay, card, { status: "won", line: "x", summary: { ...summaryBase, stage_index: 3 } },
  { stages, stats, nextScene, sessionId: "s1" });
check("won: 明日目标推荐了另一个碎片", card.querySelector(".tomorrow").textContent.includes("暮色花店"));
const kids = [...card.children].map((n) => n.className);
check("明日目标在累计之后、分隔线之前",
  kids.indexOf("tomorrow") > kids.indexOf("cume") && kids.indexOf("tomorrow") < kids.indexOf("rule"));

// —— drained 且一个词都没吃：钩子要直说返能机制
showEnding(overlay, card, { status: "drained", line: "x", summary: { ...summaryBase, vocab_hits: 0 } },
  { stages, stats, nextScene, sessionId: "s1" });
check("drained 零命中: 点破返能", card.querySelector(".tomorrow").textContent.includes("3 点能量"));

// —— 反馈控件：星级 + 文字 + 提交一次
const sent = [];
const realFetch = global.fetch;
global.fetch = async (url, opts) => { sent.push(JSON.parse(opts.body)); return { ok: true, json: async () => ({}) }; };
showEnding(overlay, card, { status: "won", line: "x", summary: { ...summaryBase, stage_index: 3 } },
  { stages, stats, nextScene, sessionId: "sess-42" });
check("反馈: 五颗星", card.querySelectorAll(".feedback .star").length === 5);
card.querySelector('.star[data-n="4"]').dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
check("反馈: 点亮四颗", card.querySelectorAll(".feedback .star.on").length === 4);
card.querySelector("#fb-text").value = "  第三幕有点卡  ";
card.querySelector("#fb-send").dispatchEvent(new dom.window.Event("click"));
await new Promise((r) => setTimeout(r, 20));
check("反馈: 发了恰好一条", sent.length === 1);
check("反馈: 载荷正确", sent[0]?.type === "feedback" && sent[0]?.session_id === "sess-42"
  && sent[0]?.payload.stars === 4 && sent[0]?.payload.text === "第三幕有点卡");
check("反馈: 提交后变已收到", card.querySelector("#feedback").textContent.includes("收到了"));

// 空反馈不发 —— 别往库里灌噪声
showEnding(overlay, card, { status: "won", line: "x", summary: { ...summaryBase, stage_index: 3 } },
  { stages, stats, nextScene, sessionId: "sess-43" });
card.querySelector("#fb-send").dispatchEvent(new dom.window.Event("click"));
await new Promise((r) => setTimeout(r, 20));
check("反馈: 空内容不发送", sent.length === 1);
check("反馈: 再来一局按钮仍在", card.querySelector("#replay") !== null);
global.fetch = realFetch;

// —— 指标内嵌按钮存在且点击不抛错
const btn = card.querySelector("#show-metrics");
check("指标按钮存在", btn !== null);
btn.dispatchEvent(new dom.window.Event("click"));
await new Promise((r) => setTimeout(r, 20));
check("指标box展开", !card.querySelector("#metrics-box").hidden);

// —— runIntro 快速通道：seen 标记后不再渲染世界观三屏
const scene = {
  scene_id: "ramen_en", fragment_code: "F-01", display_name: "雨夜拉面馆",
  target_language: "English", target_language_label: "英语", cefr_level: "A2",
  intro: [{ header: "第一屏", body: "内容" }],
  mask: { name: "加班族", brief: "b", buff: "u" },
  quest: { title: "偷汤底", objectives: ["a"], stages },
  target_vocab: ["ramen", "please"],
};
localStorage.setItem("alienlearn_seen_intro_ramen_en", "1");
const introDone = runIntro(overlay, card, scene);
await new Promise((r) => setTimeout(r, 600));   // 0.4s 短 boot 后应直落简报
check("快速通道: 直落任务简报", card.textContent.includes("任务简报"));
check("快速通道: 未渲染世界观屏", !card.textContent.includes("第一屏"));
check("简报: 全量词表", card.textContent.includes("ramen / please"));
check("简报: 返能说明", card.textContent.includes("补充全息能量"));
card.querySelector("#enter-fragment").dispatchEvent(new dom.window.Event("click"));
await introDone;
check("接入后 overlay 隐藏", overlay.hidden === true);

console.log(fails ? `\n${fails} FAILED` : "\nALL OK");
process.exit(fails ? 1 : 0);
