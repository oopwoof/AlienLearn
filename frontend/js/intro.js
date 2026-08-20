/* 开场序列与结算屏。
   开场存在的理由：新玩家不需要任何口头解释就能明白自己在干什么。
   回访玩家走快速通道 —— 世界观只值得看一次，词表值得每局看一眼。 */

import { getMetrics } from "./api.js";
import { typeOut } from "./typewriter.js";

const nextTick = (ms) => new Promise((r) => setTimeout(r, ms));

/* 按场景记「看过开场」：新场景仍然有完整的首次开场 */
const seenKey = (sceneId) => `alienlearn_seen_intro_${sceneId}`;
function hasSeenIntro(sceneId) {
  try { return localStorage.getItem(seenKey(sceneId)) === "1"; } catch { return false; }
}
function markSeenIntro(sceneId) {
  try { localStorage.setItem(seenKey(sceneId), "1"); } catch { /* 隐私模式：每次都看，不致命 */ }
}

function waitForGo(card) {
  return new Promise((resolve) => {
    const go = (e) => {
      if (e.type === "keydown" && e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      cleanup();
      resolve();
    };
    const cleanup = () => {
      card.removeEventListener("click", go);
      document.removeEventListener("keydown", go);
    };
    card.addEventListener("click", go);
    document.addEventListener("keydown", go);
  });
}

export async function runIntro(overlay, card, scene) {
  overlay.hidden = false;
  const seen = hasSeenIntro(scene.scene_id);

  // —— 接入动画。回访玩家 0.4s 短版：重看开机动画没有信息量
  card.innerHTML = `
    <div class="boot${seen ? " boot--fast" : ""}">
      <div class="boot-mark">ALIEN<span>LEARN</span></div>
      <div class="boot-sweep"></div>
      <p class="boot-status etch">正在接入全息碎片 ${scene.fragment_code}</p>
    </div>`;
  await nextTick(seen ? 400 : 1500);

  // —— 世界观导入。回访玩家整段跳过；首访玩家每屏都有「跳过」——
  //    手机上的耐心比桌面更短，三屏打字机不该是强制的
  let skipWorld = seen;
  for (const [i, screen] of scene.intro.entries()) {
    if (skipWorld) break;
    card.innerHTML = `
      <span class="eyebrow">${i + 1} / ${scene.intro.length}</span>
      <h1>${screen.header}</h1>
      <p class="body"></p>
      <div class="card-actions">
        <button class="btn" type="button">继续</button>
        <button class="btn btn--ghost" id="skip-intro" type="button">跳过 ▸</button>
      </div>`;
    const body = card.querySelector(".body");
    card.querySelector("#skip-intro").addEventListener("click", () => { skipWorld = true; }, { once: true });
    const typing = typeOut(body, screen.body);
    const fastForward = () => body._skip?.();
    card.addEventListener("click", fastForward);
    await typing;
    card.removeEventListener("click", fastForward);
    if (!skipWorld) await waitForGo(card);
  }

  // —— 任务简报。词表现在是机制（返能），全列出来，值得局前看一眼
  card.innerHTML = `
    <span class="eyebrow">任务简报</span>
    <h1>${scene.quest.title}</h1>
    <div class="brief-grid">
      <div class="brief-item">
        <span class="etch">碎片</span>
        <span class="v">${scene.display_name}<br><em>${scene.fragment_code}</em></span>
      </div>
      <div class="brief-item">
        <span class="etch">面具</span>
        <span class="v"><em>${scene.mask.name}</em><br>${scene.mask.brief}<br><span class="etch">${scene.mask.buff}</span></span>
      </div>
      <div class="brief-item">
        <span class="etch">语言层</span>
        <span class="v"><em>${scene.target_language}</em> · 难度 ${scene.cefr_level}<br>
          <span class="etch">目标词：${scene.target_vocab.join(" / ")}</span></span>
      </div>
      <div class="brief-item">
        <span class="etch">目标</span>
        <span class="v"><ol>${scene.quest.objectives.map((o) => `<li>${o}</li>`).join("")}</ol></span>
      </div>
    </div>
    <div class="rule"></div>
    <p class="body" style="min-height:0;font-size:15px">说错话不会弹出红色的叉。碎片会自己开始裂开 ——
      画面的色彩通道分离到什么程度，就是你此刻有多可疑。
      说出上面的目标词会补充全息能量：主动开口就是你在这层碎片里的呼吸方式。
      精确的语法诊断会静默滑进右侧的解密数据流，你可以不看它。</p>
    <div class="card-actions">
      <button class="btn" id="enter-fragment" type="button">接入碎片</button>
      <span class="etch">连续 3 次出戏 → 全息崩溃</span>
    </div>`;

  await new Promise((resolve) => {
    card.querySelector("#enter-fragment").addEventListener("click", () => {
      markSeenIntro(scene.scene_id);
      resolve();
    }, { once: true });
  });
  overlay.hidden = true;
}

/* --------------------------------------------------------------- 结算屏 */
const ENDING_TITLE = { won: "情报到手", crashed: "全息崩溃", drained: "能量耗尽" };
const ENDING_EYEBROW = { won: "任务完成", crashed: "伪装失效", drained: "接入中断" };
const CRASH_REASON = {
  suspicion: "伪装度崩了：语言瑕疵和出戏的积累让老板认定你不对劲。",
  strikes: "连续三次说了这家店里不存在的话 —— 碎片直接把你弹了出去。",
};

function tile([label, value, unit, hint, star]) {
  return `
    <div class="score${star ? " score--star" : ""}">
      <span class="etch">${label}</span>
      <span class="v">${value}${unit ? `<small>${unit}</small>` : ""}</span>
      ${hint ? `<span class="hint">${hint}</span>` : ""}
    </div>`;
}

/** 幕进度：三种结局共用的「你走到了哪里」。差一点和差很远必须看得出区别 */
function stageProgress(stages, summary, status) {
  if (!stages?.length) return "";
  const reached = summary.stage_index;
  const nodes = stages
    .map((s, i) => {
      const cls = status === "won" ? "done" : i < reached ? "done" : i === reached ? "now" : "";
      return `<span class="prog-node ${cls}"><i>${i + 1}</i>${s.name}</span>`;
    })
    .join(`<span class="prog-link"></span>`);
  return `<div class="prog">${nodes}</div>`;
}

export function showEnding(overlay, card, { status, line, summary }, extras = {}) {
  const { stages = [], stats = null } = extras;

  // 中段：按结局分形态。won 摆全套战绩；crashed 说清主因；drained 给距离感和下一局的钩子
  let middle = "";
  let tiles;
  if (status === "won") {
    tiles = [
      ["主动输出目标语言", summary.target_words_total, "词", "北极星指标：这一局你自己说出去多少", true],
      ["目标词收集", `${summary.vocab_hits}`, "", "", false],
      ["平均每轮", summary.target_words_per_turn, "词", "", false],
      ["语言纯度", Math.round(summary.target_language_ratio * 100), "%", "有多少轮真的在用目标语言", false],
      ["纠错触发", summary.corrections_shown, "次", "", false],
      ["出戏拦截", summary.out_of_scope_turns, "次", "", false],
      ["对话轮次", summary.turns, "", "", false],
      ["用时", summary.duration_sec, "秒", "", false],
    ];
  } else if (status === "crashed") {
    middle = `<p class="body ending-why" style="min-height:0">${CRASH_REASON[summary.crash_reason] || ""}</p>`;
    tiles = [
      ["主动输出目标语言", summary.target_words_total, "词", "北极星指标", true],
      ["出戏拦截", summary.out_of_scope_turns, "次", "", false],
      ["纠错触发", summary.corrections_shown, "次", "", false],
      ["对话轮次", summary.turns, "", "", false],
    ];
  } else {
    const remaining = Math.max(0, stages.length - 1 - summary.stage_index);
    const where = remaining === 0
      ? `能量耗尽时你已经到了最后一幕「${summary.stage_reached}」—— 就差把秘密问出口。`
      : `能量耗尽时你在「${summary.stage_reached}」，距离情报还差 ${remaining} 幕。`;
    middle = `<p class="body ending-why" style="min-height:0">${where}<br>
      <span class="etch">提示：说出目标词会补充全息能量 —— 下一局，把词表当成呼吸。</span></p>`;
    tiles = [
      ["主动输出目标语言", summary.target_words_total, "词", "北极星指标", true],
      ["目标词收集", `${summary.vocab_hits}`, "", "每个新词 +3 能量", false],
      ["对话轮次", summary.turns, "", "", false],
      ["用时", summary.duration_sec, "秒", "", false],
    ];
  }

  // 跨局累计：数据要还给产生它的人。第一局玩家没有"累计"可看，不硬凑
  let cume = "";
  if (stats && stats.sessions > 1) {
    const isRecord = summary.target_words_total > 0 && summary.target_words_total >= stats.best_words;
    cume = `<p class="cume">你的第 <b>${stats.sessions}</b> 局 · 累计输出 <b>${stats.total_target_words}</b> 词 ·
      历史最佳 <b>${stats.best_words}</b> 词${isRecord ? ` <span class="record">新纪录</span>` : ""}${
        stats.wins ? ` · 拿到秘密 ${stats.wins} 次` : ""}</p>`;
  }

  card.className = `card card--${status}`;
  card.innerHTML = `
    <span class="eyebrow">${ENDING_EYEBROW[status] || "本局结束"}</span>
    <h1>${ENDING_TITLE[status] || "本局结束"}</h1>
    <p class="body" style="min-height:0">${line}</p>
    ${stageProgress(stages, summary, status)}
    ${middle}
    <div class="scoreboard">${tiles.map(tile).join("")}</div>
    ${cume}
    <div class="rule"></div>
    <p class="body" style="min-height:0;font-size:14px">本局的纠错轨迹已匿名记录（无账号、无个人信息），
      只用来改进碎片本身。</p>
    <div class="card-actions">
      <button class="btn" id="replay" type="button">再来一局</button>
      <button class="btn btn--ghost" id="show-metrics" type="button">碎片全体数据</button>
    </div>
    <div id="metrics-box" hidden></div>`;

  overlay.hidden = false;
  card.querySelector("#replay").addEventListener("click", () => location.reload(), { once: true });

  // 累计指标：内嵌人话版，不再裸链 JSON
  card.querySelector("#show-metrics").addEventListener("click", async (e) => {
    const box = card.querySelector("#metrics-box");
    box.hidden = !box.hidden;
    if (box.hidden || box.dataset.loaded) return;
    box.textContent = "解码中…";
    const m = await getMetrics();
    if (!m?.north_star?.sessions) { box.textContent = "还没有足够的数据。"; return; }
    const ns = m.north_star;
    const outcomes = Object.entries(ns.outcomes || {})
      .map(([k, v]) => `${ENDING_TITLE[k] || k} ×${v}`).join(" · ");
    box.dataset.loaded = "1";
    box.innerHTML = `
      <div class="metrics-grid">
        <span>全部对局</span><b>${ns.sessions} 局</b>
        <span>平均主动输出</span><b>${ns.avg_target_words_per_session} 词/局</b>
        <span>平均轮次</span><b>${ns.avg_turns}</b>
        <span>结局分布</span><b>${outcomes || "—"}</b>
      </div>`;
  });
}
