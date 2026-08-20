/* 主循环：接入 → 开场 → 逐轮对话 → 结算 */

import { createSession, getMeta, getPlayerStats, sendClientEvent, streamTurn } from "./api.js";
import { mountDiorama } from "./diorama.js";
import { Hud } from "./hud.js";
import { runIntro, showEnding } from "./intro.js";
import { Typewriter } from "./typewriter.js";

const $ = (sel) => document.querySelector(sel);

const overlay = $("#overlay");
const card = $("#card");
const viewport = $("#viewport");
const transcript = $("#transcript");
const input = $("#input");
const transmit = $("#transmit");
const composer = $("#composer");
const statusLine = $("#f-status");

const hud = new Hud(document);
/* 箱庭挂载推迟到拿到场景之后（art 字段决定画哪张）。text_only 分组
   保持空实现 —— 用空对象而不是在每个调用点加 if，避免"漏一处就调到未初始化的箱庭"。 */
const NO_DIORAMA = { boot() {}, setEmotion() {}, setGlitch() {}, jolt() {}, pulse() {} };
let diorama = NO_DIORAMA;

let sessionId = null;
let scene = null;
let busy = false;
let turnNo = 0;

/* ------------------------------------------------------------------ 启动 */
async function boot() {
  let meta;
  try {
    meta = await getMeta();
  } catch (err) {
    fatal(`连不上后端：${err.message}。先启动 python backend/run.py`);
    return;
  }

  const live = meta.llm_mode === "live";
  $("#f-link-text").textContent = `链路 ${live ? meta.model : "规则桩"}`;
  $("#f-link .dot").classList.toggle("dot--mock", !live);
  $("#f-link").title = live
    ? `真实调用 ${meta.model}`
    : "MOCK 模式：三个 Agent 走本地规则桩，无需 API key。填好 .env 里的 LLM_API_KEY 即可切到真实模型。";
  // title 在触屏上永远不显示 —— mock 状态必须有可见文本，不然手机内测者
  // 分不清自己玩的是不是真模型（那一局的数据也就没法解释）
  if (!live) $("#mock-note").hidden = false;

  let payload;
  try {
    payload = await createSession(await chooseScene(meta));
  } catch (err) {
    fatal(`开局失败：${err.message}`);
    return;
  }

  scene = payload.scene;
  sessionId = payload.state.session_id;

  $("#f-fragment").textContent = scene.fragment_code;
  $("#f-mask").textContent = scene.mask.name;
  $("#f-lang").textContent = `${scene.target_language} · ${scene.cefr_level}`;
  $("#f-synth").textContent = scene.target_language.toUpperCase();
  $("#tag-text").textContent = `解码中 · ${scene.display_name}`;
  input.placeholder = `用${scene.target_language_label}说话…`;
  document.title = `AlienLearn · ${scene.display_name}`;

  hud.buildChain(scene.quest.stages);
  hud.setVocabTotal(scene.target_vocab.length);
  hud.render(payload.state);
  $("#stability-note").textContent = "接入完成。伪装尚未被质疑。";

  await runIntro(overlay, card, scene);

  // A/B（假设三：像素箱庭的 ROI）。text_only 组藏掉整个视口，
  // 只剩对话 —— 这样量出来的 session 时长差异才能归因到"空间锚点"本身。
  // 分组由后端按 player_id 哈希决定，前端只是执行，不自己随机。
  if (payload.state.variant === "text_only") {
    document.body.dataset.variant = "text_only";
    viewport.hidden = true;
  } else {
    diorama = mountDiorama(viewport, scene.art);
    diorama.boot();
    diorama.setEmotion("tired");
  }
  await openingLine();

  unlock();
  input.focus();
}

/** 场景选择。只有一个场景时不打扰；记住上次的选择 —— 回访玩家大概率还玩同一层 */
function chooseScene(meta) {
  const scenes = meta.scenes || [];
  if (scenes.length <= 1) return meta.default_scene;

  let last = null;
  try { last = localStorage.getItem("alienlearn_scene"); } catch { /* 隐私模式 */ }

  overlay.hidden = false;
  card.innerHTML = `
    <span class="eyebrow">选择碎片</span>
    <h1>接入哪一段地球？</h1>
    <div class="scene-pick">
      ${scenes
        .map(
          (s) => `
        <button class="scene-opt${s.scene_id === last ? " is-last" : ""}" data-id="${s.scene_id}" type="button">
          <b>${escapeHtml(s.display_name)}</b>
          <span class="etch">${escapeHtml(s.target_language_label)}${s.scene_id === last ? " · 上次玩过" : ""}</span>
        </button>`
        )
        .join("")}
    </div>`;

  return new Promise((resolve) => {
    card.querySelectorAll(".scene-opt").forEach((btn) =>
      btn.addEventListener("click", () => {
        try { localStorage.setItem("alienlearn_scene", btn.dataset.id); } catch { /* 同上 */ }
        resolve(btn.dataset.id);
      }, { once: true })
    );
  });
}

function openingLine() {
  const { said, tw } = addNpcLine();
  tw.push(scene.opening_line);
  tw.close();
  said.parentElement.insertAdjacentHTML(
    "beforeend",
    `<span class="stage-dir">${escapeHtml(scene.opening_stage_directions)}</span>`
  );
  return tw.finished;
}

/* ------------------------------------------------------------------ 一轮 */
composer.addEventListener("submit", (e) => {
  e.preventDefault();
  send();
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

transcript.addEventListener("click", () => currentTw?.skip());

let currentTw = null;

async function send() {
  const text = input.value.trim();
  if (busy || !text || !sessionId) return;

  lock("传输中…");
  input.value = "";
  turnNo += 1;

  const playerLine = addPlayerLine(text);
  const { said, tw } = addNpcLine();
  currentTw = tw;
  let turnErrors = [];

  const t0 = performance.now();
  const at = (label) => `${label} ${((performance.now() - t0) / 1000).toFixed(2)}s`;
  const xray = [];
  let firstToken = null;
  let ended = null;

  try {
    for await (const { event, data } of streamTurn(sessionId, text)) {
      switch (event) {
        case "route":
          xray.push(["ROUTER", `in_scope=${data.in_scope} intent=${data.intent} · ${at("")}`.trim(), false]);
          if (!data.in_scope) said.parentElement.classList.add("is-deflect");
          break;

        case "pedagogy":
          turnErrors = data.errors || [];
          renderPlayerLine(playerLine, text, turnErrors, []);
          hud.addCorrection(turnNo, data);
          xray.push([
            "PEDAGOGY",
            `severity=${data.severity} errors=${data.errors.length} · ${at("")}`.trim(),
            true,
          ]);
          if (data.degraded) systemLine(data.degraded, false);
          break;

        case "npc_delta":
          if (firstToken === null) firstToken = performance.now() - t0;
          tw.push(data.text);
          break;

        case "npc_signal":
          diorama.setEmotion(data.emotion);
          tw.close();
          xray.push([
            "PERSONA",
            `emotion=${data.emotion} quest=${data.quest_signal} · 首字 ${(firstToken / 1000 || 0).toFixed(2)}s`,
            true,
          ]);
          break;

        case "state":
          applyState(data);
          // 命中的目标词金光要等 state（后端才是命中判定的唯一口径）
          if (data.vocab_new_hits?.length) {
            renderPlayerLine(playerLine, text, turnErrors, data.vocab_new_hits);
          }
          xray.push([
            "STATE",
            `稳定度 ${data.suspicion_max - data.suspicion + data.suspicion_delta}→${data.suspicion_max - data.suspicion}` +
              ` glitch=${data.glitch_level} stage=${data.stage_name} strikes=${data.strikes}`,
            false,
          ]);
          break;

        case "ended":
          ended = data;
          break;

        case "error":
          systemLine(data.message, false);
          break;
      }
      transcript.scrollTop = transcript.scrollHeight;
    }
  } catch (err) {
    systemLine(`传输失败：${err.message}`, false);
  }

  tw.close();
  hud.addXray(turnNo, xray);
  await tw.finished;
  currentTw = null;
  transcript.scrollTop = transcript.scrollHeight;

  if (ended) {
    systemLine(ended.line, ended.status === "won");
    diorama.setGlitch(ended.status === "won" ? 0 : 3);
    if (ended.status !== "won") diorama.jolt();
    lock(ended.status === "won" ? "任务完成" : "本局结束");
    // 跨局累计趁这 1.7s 的余韵取回来：session_end 已落库，包含本局
    const stats = getPlayerStats();
    setTimeout(async () => {
      showEnding(overlay, card, ended, { stages: scene.quest.stages, stats: await stats });
    }, 1700);
    return;
  }

  unlock();
  input.focus();
}

function applyState(state) {
  hud.render(state);
  diorama.setGlitch(state.glitch_level);
  if (state.suspicion_delta >= 12) diorama.jolt();
  // 正向反馈链：负向有 jolt/色差，正向必须有等重的存在感 ——
  // HUD 提示两臂共享，暖色脉冲只属于箱庭臂（text_only 的 pulse 是空实现）
  if (state.vocab_new_hits?.length) {
    hud.noteVocab(state.vocab_new_hits, state.energy_refund);
    diorama.pulse();
  }
  $("#tag-text").textContent =
    `解码中 · ${state.stage_name} ${state.stage_index + 1}/${state.stage_total}`;
}

/* ------------------------------------------------------- 记录区的三种声音 */
function addNpcLine() {
  const wrap = document.createElement("div");
  wrap.className = "line line--npc";
  wrap.innerHTML = `<span class="speaker">${escapeHtml(scene?.npc_name || "NPC")}</span><span class="said"></span>`;
  transcript.appendChild(wrap);
  transcript.scrollTop = transcript.scrollHeight;
  const said = wrap.querySelector(".said");
  return { said, tw: new Typewriter(said, { cps: 46 }) };
}

function addPlayerLine(text) {
  const wrap = document.createElement("div");
  wrap.className = "line line--player";
  wrap.innerHTML = `<span class="speaker">合成器 · 你</span><span class="said">${escapeHtml(text)}</span>`;
  transcript.appendChild(wrap);
  transcript.scrollTop = transcript.scrollHeight;
  return wrap.querySelector(".said");
}

function systemLine(text, good) {
  const wrap = document.createElement("div");
  wrap.className = `line line--system${good ? " is-good" : ""}`;
  wrap.innerHTML = `<span class="said">${escapeHtml(text)}</span>`;
  transcript.appendChild(wrap);
  transcript.scrollTop = transcript.scrollHeight;
}

/** 玩家原句的双色渲染：瑕疵片段做色差（.flaw），首次命中的目标词发金光（.gleam）。

    先在原始文本上定位区间、再逐片转义拼装。旧实现是在转义后的 HTML 里
    includes(转义后的 span)：大小写、多余空格、跨转义实体，任何一个不对齐就
    静默不高亮 —— 而"span 错了"在屏幕上和"没有错误"长得一模一样，线上评测都发现不了。
    所以匹配失败现在必须上报（手机内测者不会开控制台，console.warn 等于没说）。 */
function renderPlayerLine(el, text, errors, hits) {
  const ranges = [];

  for (const err of errors || []) {
    const span = String(err.span || "").trim();
    if (!span) continue;
    const found = findRanges(text, spanPattern(span));
    if (!found.length) {
      console.warn("[flaw] span 未能定位到原句：", span);
      sendClientEvent(sessionId, "span_match_failed", { span: span.slice(0, 120), turn: turnNo });
      continue;
    }
    for (const r of found) addRange(ranges, { ...r, cls: "flaw" });
  }
  for (const word of hits || []) {
    for (const r of findRanges(text, vocabPattern(word))) {
      addRange(ranges, { ...r, cls: "gleam" }); // 与 flaw 重叠时缺陷优先（先加的赢）
    }
  }

  ranges.sort((a, b) => a.start - b.start);
  let html = "";
  let cursor = 0;
  for (const r of ranges) {
    html += escapeHtml(text.slice(cursor, r.start));
    html += `<span class="${r.cls}">${escapeHtml(text.slice(r.start, r.end))}</span>`;
    cursor = r.end;
  }
  html += escapeHtml(text.slice(cursor));
  el.innerHTML = html;
}

function addRange(ranges, next) {
  if (ranges.some((r) => next.start < r.end && r.start < next.end)) return;
  ranges.push(next);
}

/** span → 大小写不敏感、空白归一的正则（找出所有出现处，不止第一处） */
function spanPattern(span) {
  const escaped = span.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+");
  return new RegExp(escaped, "gi");
}

/** 目标词 → 整词 + s/es 复数容错，与后端 lang_utils.match_target_vocab 同口径。
    日语词没有 \b 可用，退回子串匹配。 */
function vocabPattern(word) {
  const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return /^[\x00-\x7F]+$/.test(word)
    ? new RegExp(`\\b${escaped}(?:es|s)?\\b`, "gi")
    : new RegExp(escaped, "g");
}

function findRanges(text, re) {
  const out = [];
  let m;
  while ((m = re.exec(text)) !== null) {
    if (!m[0].length) { re.lastIndex += 1; continue; }
    out.push({ start: m.index, end: m.index + m[0].length });
  }
  return out;
}

/* ------------------------------------------------------------------ 杂项 */
function lock(msg) {
  busy = true;
  input.disabled = true;
  transmit.disabled = true;
  composer.classList.add("is-locked");
  statusLine.textContent = msg || "";
}

function unlock() {
  busy = false;
  input.disabled = false;
  transmit.disabled = false;
  composer.classList.remove("is-locked");
  statusLine.textContent = `第 ${turnNo + 1} 轮`;
}

function fatal(msg) {
  overlay.hidden = false;
  card.innerHTML = `<span class="eyebrow">接入失败</span><h1>链路中断</h1>
    <p class="body" style="min-height:0">${escapeHtml(msg)}</p>`;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* ------------------------------------------------------------ 手机适配 */
/* iOS 键盘：Safari 弹键盘时不改 window.innerHeight，只改 visualViewport ——
   唯一确定性的办法是把布局容器钳到可视高度（--vvh），输入框才永远可见。
   否掉 scrollIntoView 方案：它和 iOS 自身的 focus 滚动竞争，时序脆弱。
   用 matchMedia 门控，桌面路径零改动。 */
const mobileMq = window.matchMedia("(max-width: 768px)");
(function bindViewportClamp() {
  const vv = window.visualViewport;
  if (!vv) return; // 降级链的下一层是 CSS 的 100dvh
  const apply = () => {
    if (!mobileMq.matches) {
      document.documentElement.style.removeProperty("--vvh");
      return;
    }
    document.documentElement.style.setProperty("--vvh", `${Math.round(vv.height)}px`);
    window.scrollTo(0, 0);                       // 抵消 iOS 的自动滚动
    transcript.scrollTop = transcript.scrollHeight;
  };
  vv.addEventListener("resize", apply);
  vv.addEventListener("scroll", apply);
  mobileMq.addEventListener?.("change", apply);
  apply();
})();

/* 完整仪器轨在手机上收进底部抽屉 */
$("#rail-toggle").addEventListener("click", () => {
  const open = document.body.classList.toggle("rail-open");
  $("#rail-toggle").textContent = open ? "收起 ▴" : "仪器 ▾";
});

$("#mock-note-close").addEventListener("click", () => {
  $("#mock-note").hidden = true;
});

/* 架构透视开关 */
const xrayPanel = $("#xray");
const xrayToggle = $("#xray-toggle");
xrayToggle.addEventListener("click", () => {
  const open = xrayPanel.hidden;
  xrayPanel.hidden = !open;
  xrayToggle.setAttribute("aria-pressed", String(open));
});
$("#xray-close").addEventListener("click", () => {
  xrayPanel.hidden = true;
  xrayToggle.setAttribute("aria-pressed", "false");
});

boot();
