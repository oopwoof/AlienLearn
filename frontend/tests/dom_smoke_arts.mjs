/* 全部场景美术的 jsdom 挂载冒烟：结构约定（js-boss/js-face/pulse-layer）+ 表情切换。
   美术的硬约定失效时是静默的 —— 少了 js-face 只是表情不会变，画面照样渲染出来，
   所以每加一套美术都必须过这一关。 */
import { JSDOM } from "jsdom";

// 路径相对本文件解析：脚本收进仓库后不该再依赖某台机器的盘符
const src = (p) => new URL(`../js/${p}`, import.meta.url).href;

const dom = new JSDOM(`<!doctype html><body><div id="v1"></div><div id="v2"></div><div id="v3"></div></body>`);
global.window = dom.window;
global.document = dom.window.document;

const { mountDiorama } = await import(src("diorama.js"));

let fails = 0;
const check = (n, c) => { if (!c) { fails++; console.log("X  " + n); } else console.log("OK " + n); };

for (const [id, art] of [["#v1", "ramen"], ["#v2", "flower"], ["#v3", "bookshop"]]) {
  const vp = document.querySelector(id);
  const d = mountDiorama(vp, art);
  check(`${art}: 两个通道层`, vp.querySelectorAll(".chan").length === 2);
  check(`${art}: pulse 层`, vp.querySelector(".pulse-layer") !== null);
  check(`${art}: js-boss ×2`, vp.querySelectorAll(".js-boss").length === 2);
  check(`${art}: js-face ×2`, vp.querySelectorAll(".js-face").length === 2);
  check(`${art}: svg 存在`, vp.querySelectorAll("svg").length === 2);
  d.setEmotion("conspiratorial");
  check(`${art}: lean 生效`, vp.querySelector(".js-boss").classList.contains("lean"));
  d.setEmotion("warm");
  check(`${art}: lean 撤销`, !vp.querySelector(".js-boss").classList.contains("lean"));
  d.setGlitch(2);
  // jsdom 里 clientWidth=0 → 视口缩放钳到 2 倍：4px × 2 = 8.0px
  check(`${art}: --ab 设置(含小屏缩放)`, vp.style.getPropertyValue("--ab") === "8.0px");
  d.pulse();
  check(`${art}: pulse class`, vp.querySelector(".pulse-layer").classList.contains("pulse"));
  // 所有 rect 坐标都在 160×90 画布内
  let out = 0;
  vp.querySelectorAll("svg rect").forEach((r) => {
    const x = +r.getAttribute("x"), y = +r.getAttribute("y");
    const w = +(r.getAttribute("width") || 0), h = +(r.getAttribute("height") || 0);
    if (x < 0 || y < 0 || x + w > 160 || y + h > 90) out++;
  });
  check(`${art}: 无越界 rect`, out === 0);
  // SVG 里不能用 id：同一段画面在页面里存在两份，id 会重复
  check(`${art}: 无 id 属性`, vp.querySelectorAll("svg [id]").length === 0);
}

// 未知 art 回落 ramen 不炸
const vp3 = document.createElement("div");
document.body.appendChild(vp3);
mountDiorama(vp3, "nope");
check("未知 art 回落", vp3.querySelectorAll(".chan").length === 2);

console.log(fails ? `\n${fails} FAILED` : "\nALL OK");
process.exit(fails ? 1 : 0);
