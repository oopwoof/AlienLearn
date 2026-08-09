/* 主循环：接入 → 开场 → 逐轮对话 → 结算 */

import { createSession, getMeta, streamTurn } from "./api.js";
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
const diorama = mountDiorama(viewport);

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

  let payload;
  try {
    payload = await createSession(meta.default_scene);
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
  hud.render(payload.state);
  $("#stability-note").textContent = "接入完成。伪装尚未被质疑。";

  await runIntro(overlay, card, scene);

  diorama.boot();
  diorama.setEmotion("tired");
  await openingLine();

  unlock();
  input.focus();
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
          markFlaws(playerLine, text, data.errors);
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
    setTimeout(() => showEnding(overlay, card, ended), 1700);
    return;
  }

  unlock();
  input.focus();
}

function applyState(state) {
  hud.render(state);
  diorama.setGlitch(state.glitch_level);
  if (state.suspicion_delta >= 12) diorama.jolt();
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

/** 被诊断的片段不打红叉，给它做色差 —— 在这个世界里，错误是信号缺陷 */
function markFlaws(el, text, errors) {
  if (!errors?.length) return;
  let html = escapeHtml(text);
  for (const err of errors) {
    const span = escapeHtml(String(err.span || "").trim());
    if (!span || !html.includes(span)) continue;
    html = html.replace(span, `<span class="flaw">${span}</span>`);
  }
  el.innerHTML = html;
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
