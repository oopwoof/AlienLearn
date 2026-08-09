/* 开场序列与结算屏。
   开场存在的理由：面试官/新玩家不需要任何口头解释就能明白自己在干什么。 */

import { typeOut } from "./typewriter.js";

const nextTick = (ms) => new Promise((r) => setTimeout(r, ms));

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

  // —— 接入动画
  card.innerHTML = `
    <div class="boot">
      <div class="boot-mark">ALIEN<span>LEARN</span></div>
      <div class="boot-sweep"></div>
      <p class="boot-status etch">正在接入全息碎片 ${scene.fragment_code}</p>
    </div>`;
  await nextTick(1500);

  // —— 世界观导入
  for (const [i, screen] of scene.intro.entries()) {
    card.innerHTML = `
      <span class="eyebrow">${i + 1} / ${scene.intro.length}</span>
      <h1>${screen.header}</h1>
      <p class="body"></p>
      <div class="card-actions">
        <button class="btn" type="button">继续</button>
        <span class="etch">Enter 或点击任意处</span>
      </div>`;
    const body = card.querySelector(".body");
    await typeOut(body, screen.body);
    await waitForGo(card);
  }

  // —— 任务简报
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
          <span class="etch">用词参考：${scene.target_vocab.slice(0, 8).join(" / ")}</span></span>
      </div>
      <div class="brief-item">
        <span class="etch">目标</span>
        <span class="v"><ol>${scene.quest.objectives.map((o) => `<li>${o}</li>`).join("")}</ol></span>
      </div>
    </div>
    <div class="rule"></div>
    <p class="body" style="min-height:0;font-size:15px">说错话不会弹出红色的叉。碎片会自己开始裂开 ——
      画面的色彩通道分离到什么程度，就是你此刻有多可疑。
      精确的语法诊断会静默滑进右侧的解密数据流，你可以不看它。</p>
    <div class="card-actions">
      <button class="btn" id="enter-fragment" type="button">接入碎片</button>
      <span class="etch">连续 3 次出戏 → 全息崩溃</span>
    </div>`;

  await new Promise((resolve) => {
    card.querySelector("#enter-fragment").addEventListener("click", resolve, { once: true });
  });
  overlay.hidden = true;
}

/* --------------------------------------------------------------- 结算屏 */
const ENDING_TITLE = {
  won: "情报到手",
  crashed: "全息崩溃",
  drained: "能量耗尽",
};

const ENDING_EYEBROW = {
  won: "任务完成",
  crashed: "伪装失效",
  drained: "接入中断",
};

export function showEnding(overlay, card, { status, line, summary }) {
  const tiles = [
    ["主动输出目标语言", summary.target_words_total, "词", "北极星指标：这一局你自己说出去多少", true],
    ["平均每轮", summary.target_words_per_turn, "词", "", false],
    ["语言纯度", Math.round(summary.target_language_ratio * 100), "%", "有多少轮真的在用目标语言", false],
    ["纠错触发", summary.corrections_shown, "次", "", false],
    ["全息异变", summary.glitch_events, "次", "被 Glitch 惩罚的轮次", false],
    ["出戏拦截", summary.out_of_scope_turns, "次", "Router 拦下的越狱/离题", false],
    ["对话轮次", summary.turns, "", "", false],
    ["用时", summary.duration_sec, "秒", "", false],
  ];

  card.innerHTML = `
    <span class="eyebrow">${ENDING_EYEBROW[status] || "本局结束"}</span>
    <h1>${ENDING_TITLE[status] || "本局结束"}</h1>
    <p class="body" style="min-height:0">${line}</p>
    <div class="scoreboard">
      ${tiles
        .map(
          ([label, value, unit, hint, star]) => `
        <div class="score${star ? " score--star" : ""}">
          <span class="etch">${label}</span>
          <span class="v">${value}${unit ? `<small>${unit}</small>` : ""}</span>
          ${hint ? `<span class="hint">${hint}</span>` : ""}
        </div>`
        )
        .join("")}
    </div>
    <div class="rule"></div>
    <p class="body" style="min-height:0;font-size:14px">本局每一轮的纠错轨迹已写入 <code>data/telemetry.db</code>：
      玩家原句 → 路由判定 → 结构化纠错 → 人设化反馈 → 状态结算。
      这才是产品沉淀下来的数据资产，不是聊天记录。</p>
    <div class="card-actions">
      <button class="btn" id="replay" type="button">再来一局</button>
      <a class="btn btn--ghost" href="/api/metrics" target="_blank" rel="noopener">查看累计指标</a>
    </div>`;

  overlay.hidden = false;
  card.querySelector("#replay").addEventListener("click", () => location.reload(), { once: true });
}
