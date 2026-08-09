/* 仪器轨。只负责把后端状态画出来 —— 不做任何判断，判断都在后端状态机里。 */

const SEG = 20;

const SEV_LABEL = { none: "clean", minor: "minor", major: "major" };

export class Hud {
  constructor(root) {
    this.stabBar = root.querySelector("#stability-bar");
    this.stabVal = root.querySelector("#stability-val");
    this.stabGauge = root.querySelector("#stability-gauge");
    this.stabNote = root.querySelector("#stability-note");
    this.energyBar = root.querySelector("#energy-bar");
    this.energyVal = root.querySelector("#energy-val");
    this.strikes = root.querySelector("#strikes");
    this.chain = root.querySelector("#quest-chain ol");
    this.decrypt = root.querySelector("#decrypt-list");
    this.xrayList = document.querySelector("#xray-list");

    this._segments(this.stabBar);
    this._segments(this.energyBar);
  }

  _segments(bar) {
    bar.innerHTML = Array.from({ length: SEG }, () => "<i></i>").join("");
  }

  _fill(bar, ratio) {
    const on = Math.round(ratio * SEG);
    bar.querySelectorAll("i").forEach((seg, i) => seg.classList.toggle("on", i < on));
  }

  /** 全息稳定度 = 100 - 伪装度。填满是好事，符合玩家直觉 */
  render(state) {
    const stability = state.suspicion_max - state.suspicion;
    this.stabVal.innerHTML = `${stability}<small> / ${state.suspicion_max}</small>`;
    this.stabGauge.dataset.band = String(state.glitch_level);
    this._fill(this.stabBar, stability / state.suspicion_max);

    this.energyVal.innerHTML = `${state.energy}<small> / ${state.energy_max}</small>`;
    this._fill(this.energyBar, state.energy / state.energy_max);

    this.strikes.querySelectorAll("i").forEach((box, i) => box.classList.toggle("on", i < state.strikes));

    if (state.reasons?.length) {
      const delta = state.suspicion_delta;
      // 面板读的是稳定度，所以符号要翻过来：伪装度 +14 等于稳定度 −14
      const cls = delta > 0 ? "" : ' class="good"';
      const sign = delta === 0 ? "±" : delta > 0 ? "−" : "+";
      this.stabNote.innerHTML =
        `<b${cls}>${sign}${Math.abs(delta)}</b> ${state.reasons.join(" · ")}`;
    }

    this.chain.querySelectorAll("li").forEach((li, i) => {
      li.classList.toggle("done", i < state.stage_index);
      li.classList.toggle("now", i === state.stage_index);
    });
  }

  buildChain(stages) {
    this.chain.innerHTML = stages
      .map((s, i) => `<li><span class="node">${i + 1}</span><span>${s.name}</span></li>`)
      .join("");
  }

  /** 纠错只在有瑕疵时进流 —— 它是一份缺陷日志，不是鼓励播报 */
  addCorrection(turn, pedagogy) {
    if (!pedagogy.errors?.length) return;
    this.decrypt.querySelector(".decrypt-empty")?.remove();

    const rows = pedagogy.errors
      .map(
        (e) => `<div class="fix">
            <span class="was">${escape(e.span)}</span><span class="arrow">▸</span><span class="now">${escape(e.fix)}</span>
          </div>
          <div class="note">${escape(e.note)}</div>`
      )
      .join("");

    const entry = document.createElement("div");
    entry.className = "entry";
    entry.dataset.sev = pedagogy.severity;
    entry.innerHTML = `
      <div class="entry-head">
        <span class="entry-turn">T${turn}</span>
        <span class="entry-sev">${SEV_LABEL[pedagogy.severity] || pedagogy.severity}</span>
      </div>${rows}`;
    this.decrypt.prepend(entry);
  }

  /** 架构透视：给"看架构的那个观众"用，默认关闭 */
  addXray(turn, rows) {
    const block = document.createElement("div");
    block.className = "xray-turn";
    block.innerHTML =
      `<span class="etch">turn ${turn}</span>` +
      rows
        .map(
          ([agent, text, parallel]) =>
            `<div class="xray-row${parallel ? " is-parallel" : ""}"><span>${agent}</span><span>${escape(text)}</span></div>`
        )
        .join("");
    this.xrayList.prepend(block);
  }
}

function escape(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
