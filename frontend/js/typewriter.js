/* 打字机。字符进队列、按固定速率吐出 ——
   这样无论后端是流式（live）还是整块（mock），前端节奏都一致。 */

const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export class Typewriter {
  constructor(el, { cps = 42, caret = true } = {}) {
    this.el = el;
    this.interval = 1000 / cps;
    this.queue = "";
    this.streamClosed = false;
    this.timer = null;
    this.caretEl = null;
    if (caret && !REDUCED) {
      this.caretEl = document.createElement("i");
      this.caretEl.className = "caret";
      this.el.appendChild(this.caretEl);
    }
    this._resolve = null;
    this.finished = new Promise((r) => { this._resolve = r; });
  }

  push(text) {
    this.queue += text;
    if (REDUCED) return this._drainAll();
    if (!this.timer) this.timer = setInterval(() => this._tick(), this.interval);
  }

  /** 后端不再有新增量了 */
  close() {
    this.streamClosed = true;
    if (REDUCED || !this.queue) this._drainAll();
  }

  /** 玩家点了一下屏幕：立刻把剩下的字全吐出来 */
  skip() { this._drainAll(); }

  _tick() {
    if (!this.queue) {
      if (this.streamClosed) this._drainAll();
      return;
    }
    this._write(this.queue[0]);
    this.queue = this.queue.slice(1);
  }

  _write(chars) {
    const node = document.createTextNode(chars);
    if (this.caretEl) this.el.insertBefore(node, this.caretEl);
    else this.el.appendChild(node);
  }

  _drainAll() {
    if (this.queue) {
      this._write(this.queue);
      this.queue = "";
    }
    if (!this.streamClosed) return;
    clearInterval(this.timer);
    this.timer = null;
    this.caretEl?.remove();
    this.caretEl = null;
    this._resolve?.();
    this._resolve = null;
  }
}

/** 覆盖层用的一次性打字：整段文字，返回 Promise */
export function typeOut(el, text, { cps = 55 } = {}) {
  el.textContent = "";
  if (REDUCED) {
    el.textContent = text;
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    let i = 0;
    const step = setInterval(() => {
      el.textContent = text.slice(0, ++i);
      if (i >= text.length) { clearInterval(step); resolve(); }
    }, 1000 / cps);
    el._skip = () => { clearInterval(step); el.textContent = text; resolve(); };
  });
}
