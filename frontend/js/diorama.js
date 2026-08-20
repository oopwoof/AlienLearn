/* ============================================================
   像素箱庭：挂载与控制。
   它存在的理由不是"提供跑图玩法"，而是给玩家一个零认知成本的空间锚点 ——
   免掉"想象我在哪"的脑力开销，把注意力全部留给语言博弈。

   场景美术在 art/ 目录按 scene JSON 的 art 字段路由；每张画都被克隆成
   两层（红通道 / 青通道），由 CSS 的 --ab 决定分离距离。
   所以美术里不能用 id，只能用 class：同一段 SVG 在页面里存在两份。
   美术的两个硬约定：NPC 根组带 class js-boss、脸部子组带 js-face
   （表情几何见 art/faces.js）。
   ============================================================ */

import { FACES } from "./art/faces.js";
import { flowerArt } from "./art/flower.js";
import { ramenArt } from "./art/ramen.js";

const ARTS = { ramen: ramenArt, flower: flowerArt };

const AB_BY_LEVEL = [0, 1.5, 4, 8];   // 每档 Glitch 的通道分离像素

export function mountDiorama(viewport, artId = "ramen") {
  let art = ARTS[artId];
  if (!art) {
    console.warn(`[diorama] 未知的场景美术 "${artId}"，回落 ramen`);
    art = ARTS.ramen;
  }
  const html = art();
  viewport.insertAdjacentHTML(
    "afterbegin",
    `<div class="chan chan--gb">${html}</div><div class="chan chan--r">${html}</div><div class="pulse-layer"></div>`
  );

  const faces = viewport.querySelectorAll(".js-face");
  const bosses = viewport.querySelectorAll(".js-boss");
  const pulseLayer = viewport.querySelector(".pulse-layer");
  let joltTimer = null;
  let pulseTimer = null;

  return {
    setEmotion(emotion) {
      const markup = FACES[emotion] || FACES.tired;
      faces.forEach((g) => { g.innerHTML = markup; });
      bosses.forEach((g) => g.classList.toggle("lean", emotion === "conspiratorial"));
    },

    /** 伪装度掉档 → 两个色彩通道分开。视觉惩罚就是渲染管线本身。 */
    setGlitch(level) {
      const ab = AB_BY_LEVEL[Math.min(3, Math.max(0, level))];
      viewport.style.setProperty("--ab", `${ab}px`);
      viewport.style.setProperty("--tear", level >= 2 ? "1" : "0");
    },

    jolt() {
      viewport.classList.remove("jolt");
      void viewport.offsetWidth;             // 强制重排，让动画能重复触发
      viewport.classList.add("jolt");
      clearTimeout(joltTimer);
      joltTimer = setTimeout(() => viewport.classList.remove("jolt"), 400);
    },

    /** 命中目标词的暖色脉冲 —— jolt 的镜像：那个冷而抖，这个暖而稳。
        负向惩罚有渲染管线级的存在感，正向奖励不能只是"什么都没发生"。 */
    pulse() {
      pulseLayer.classList.remove("pulse");
      void pulseLayer.offsetWidth;
      pulseLayer.classList.add("pulse");
      clearTimeout(pulseTimer);
      pulseTimer = setTimeout(() => pulseLayer.classList.remove("pulse"), 700);
    },

    boot() {
      viewport.classList.add("booting");
      setTimeout(() => viewport.classList.remove("booting"), 950);
    },
  };
}
