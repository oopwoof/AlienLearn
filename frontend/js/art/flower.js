/* 像素箱庭 · 暮色花店（160 × 90 逻辑像素，手写 rect）。
   与拉面馆共享 NPC 头部几何（faces.js），只换发型、衣着和环境 ——
   调色板刻意反着来：拉面馆是暖橙雨夜，这里是暮色紫 + 苔绿 + 花的亮色。 */

import { FACES } from "./faces.js";

const W = 160;
const H = 90;

/* 一簇花：三四个色块叠出来的团，比逐瓣画省 10 倍且远看更像花 */
function bloom(x, y, main, dark) {
  return `
    <rect x="${x}" y="${y}" width="6" height="4" fill="${main}"/>
    <rect x="${x + 1}" y="${y - 2}" width="4" height="2" fill="${main}"/>
    <rect x="${x + 4}" y="${y + 1}" width="3" height="2" fill="${dark}"/>
    <rect x="${x - 1}" y="${y + 2}" width="2" height="2" fill="${dark}"/>`;
}

function bucket(x, y, w) {
  return `
    <rect x="${x}" y="${y}" width="${w}" height="9" fill="#4A5460"/>
    <rect x="${x}" y="${y}" width="${w}" height="1" fill="#5E6A78"/>
    <rect x="${x}" y="${y + 8}" width="${w}" height="1" fill="#39424C"/>`;
}

function petals() {
  const spots = [
    [58, 20], [72, 26], [88, 18], [104, 24], [118, 21], [66, 32], [96, 30], [112, 34],
  ];
  return spots
    .map(([x, y], i) => `<rect class="drop" style="animation-delay:${(i * 0.23).toFixed(2)}s" x="${x}" y="${y}" width="2" height="2" fill="#D66A8C"/>`)
    .join("");
}

function mist() {
  return [0, 0.7, 1.4]
    .map((d, i) => `<rect class="puff" style="animation-delay:${d}s" x="${58 + i * 3}" y="38" width="3" height="3" fill="#DCE8DC" opacity="0"/>`)
    .join("");
}

export function flowerArt() {
  return `
<svg viewBox="0 0 ${W} ${H}" shape-rendering="crispEdges" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
  <!-- 底 -->
  <rect x="0" y="0" width="${W}" height="${H}" fill="#131018"/>
  <!-- 后墙：苔绿 -->
  <rect x="0" y="10" width="${W}" height="50" fill="#26301F"/>
  <rect x="0" y="10" width="${W}" height="2" fill="#33402A"/>

  <!-- 店灯的暖光落点 -->
  <rect x="46" y="12" width="70" height="20" fill="#E8C05A" opacity=".07"/>

  <!-- 左窗：外面是暮色。卷帘拉了一半 —— 快打烊了 -->
  <rect x="6" y="16" width="44" height="32" fill="#1E2418"/>
  <rect x="8" y="18" width="40" height="28" fill="#3A2A4E"/>
  <rect x="8" y="36" width="40" height="4" fill="#C46A5A" opacity=".55"/>
  <rect x="8" y="40" width="40" height="6" fill="#241B33"/>
  <rect x="12" y="38" width="8" height="4" fill="#241B33"/>
  <rect x="30" y="37" width="10" height="5" fill="#241B33"/>
  <rect x="8" y="18" width="40" height="7" fill="#2A3326"/>
  <rect x="8" y="24" width="40" height="1" fill="#1E2418"/>
  <rect x="8" y="21" width="40" height="1" fill="#232B20"/>
  <rect x="27" y="25" width="2" height="21" fill="#1E2418"/>

  <!-- 天花板 + 吊着的植物 -->
  <rect x="0" y="0" width="${W}" height="10" fill="#181320"/>
  <rect x="14" y="0" width="1" height="6" fill="#2A2118"/>
  <rect x="10" y="6" width="9" height="4" fill="#8A5A38"/>
  <rect x="9" y="10" width="3" height="5" fill="#4A6B38"/>
  <rect x="16" y="10" width="3" height="7" fill="#35502A"/>
  <rect x="130" y="0" width="1" height="5" fill="#2A2118"/>
  <rect x="126" y="5" width="9" height="4" fill="#8A5A38"/>
  <rect x="125" y="9" width="3" height="6" fill="#4A6B38"/>
  <rect x="132" y="9" width="3" height="8" fill="#35502A"/>

  <!-- 店灯（暖，微弱呼吸） -->
  <rect x="79" y="0" width="1" height="5" fill="#2A2118"/>
  <rect class="glow" x="68" y="3" width="23" height="14" fill="#E8C05A" opacity=".14"/>
  <rect x="74" y="5" width="11" height="6" fill="#6B5A34"/>
  <rect class="flicker" x="76" y="7" width="7" height="4" fill="#FFE9B8"/>

  <!-- 右墙花架：两层，摆满打烊前的存货 -->
  <rect x="124" y="26" width="35" height="2" fill="#5B4327"/>
  <rect x="124" y="44" width="35" height="2" fill="#5B4327"/>
  ${bloom(127, 21, "#D66A8C", "#A84860")}
  ${bloom(137, 20, "#E8C05A", "#B88A32")}
  ${bloom(148, 22, "#8A6BB0", "#64488A")}
  <rect x="128" y="25" width="3" height="1" fill="#4A6B38"/>
  <rect x="139" y="24" width="3" height="2" fill="#4A6B38"/>
  ${bloom(128, 39, "#A83A48", "#7A2834")}
  ${bloom(140, 38, "#D66A8C", "#A84860")}
  ${bloom(150, 40, "#EDE8E2", "#B8B2A6")}
  <rect x="131" y="43" width="3" height="1" fill="#35502A"/>
  <rect x="144" y="42" width="2" height="2" fill="#35502A"/>

  <!-- 橱窗边的白山茶：故事物件，全画面最亮的白，谁都会先看到它 -->
  <rect x="54" y="52" width="18" height="8" fill="#39424C"/>
  <rect x="54" y="52" width="18" height="1" fill="#4A5460"/>
  ${bloom(56, 44, "#F2EEE6", "#C6BFB4")}
  ${bloom(63, 42, "#F2EEE6", "#C6BFB4")}
  <rect x="59" y="48" width="2" height="4" fill="#35502A"/>
  <rect x="65" y="47" width="2" height="5" fill="#35502A"/>
  <rect x="61" y="49" width="3" height="1" fill="#4A6B38"/>
  ${mist()}

  <!-- 左下花桶：待售的存货 -->
  ${bloom(10, 46, "#D66A8C", "#A84860")}
  ${bloom(19, 44, "#E8C05A", "#B88A32")}
  <rect x="13" y="50" width="2" height="3" fill="#35502A"/>
  <rect x="21" y="49" width="2" height="4" fill="#35502A"/>
  ${bucket(8, 52, 20)}

  <!-- 飘落的花瓣（复用雨滴的下落动画） -->
  ${petals()}

  <!-- Marisol：银发挽髻，梅子色罩衫 + 苔绿围裙。头部网格与拉面馆完全一致 -->
  <g class="js-boss boss">
    <rect x="76" y="45" width="7" height="15" fill="#6E4A56"/>
    <rect x="117" y="45" width="7" height="15" fill="#6E4A56"/>
    <rect x="76" y="56" width="7" height="4" fill="#B8865C"/>
    <rect x="117" y="56" width="7" height="4" fill="#B8865C"/>
    <rect x="82" y="43" width="36" height="17" fill="#6E4A56"/>
    <rect x="86" y="46" width="28" height="14" fill="#47603A"/>
    <rect x="94" y="46" width="2" height="14" fill="#3A5030"/>
    <rect x="105" y="46" width="2" height="14" fill="#3A5030"/>
    <rect x="86" y="40" width="28" height="3" fill="#E8DCC8"/>
    <rect x="96" y="38" width="8" height="3" fill="#A87548"/>
    <rect x="91" y="23" width="18" height="16" fill="#C89468"/>
    <rect x="91" y="23" width="2" height="16" fill="#A87548"/>
    <rect x="89" y="24" width="2" height="9" fill="#C6BFB4"/>
    <rect x="109" y="24" width="2" height="9" fill="#C6BFB4"/>
    <rect x="90" y="16" width="20" height="7" fill="#C6BFB4"/>
    <rect x="96" y="12" width="8" height="4" fill="#C6BFB4"/>
    <rect x="96" y="15" width="8" height="1" fill="#A8A296"/>
    <rect x="103" y="13" width="2" height="2" fill="#D66A8C"/>
    <rect x="89" y="21" width="22" height="2" fill="#B2AB9E"/>
    <g class="js-face">${FACES.tired}</g>
  </g>

  <!-- 柜台：包花的操作台 -->
  <rect x="0" y="60" width="${W}" height="5" fill="#7A6844"/>
  <rect x="0" y="60" width="${W}" height="1" fill="#96703F"/>
  <rect x="0" y="64" width="${W}" height="1" fill="#3E3626"/>
  <rect x="0" y="65" width="${W}" height="8" fill="#4C4030"/>
  <rect x="0" y="70" width="${W}" height="3" fill="#352D20"/>
  <rect x="34" y="65" width="1" height="5" fill="#3E3626"/>
  <rect x="100" y="65" width="1" height="5" fill="#3E3626"/>
  <!-- 牛皮纸卷 + 搁下的剪刀 -->
  <rect x="126" y="55" width="22" height="4" fill="#C9BEAA"/>
  <rect x="126" y="55" width="22" height="1" fill="#DED2BE"/>
  <rect x="147" y="54" width="2" height="6" fill="#8A5A38"/>
  <rect x="36" y="61" width="12" height="1" fill="#8A8A96"/>
  <rect x="40" y="59" width="1" height="4" fill="#8A8A96"/>
  <rect x="34" y="62" width="3" height="2" fill="#A83A48"/>

  <!-- 前景：柜台外侧。没包完的那束花躺在这 -->
  <rect x="0" y="73" width="${W}" height="17" fill="#151119"/>
  <rect x="16" y="79" width="26" height="5" fill="#C9BEAA"/>
  <rect x="20" y="77" width="22" height="2" fill="#B8AE9A"/>
  <rect x="16" y="83" width="26" height="1" fill="#8A836F"/>
  ${bloom(40, 74, "#D66A8C", "#A84860")}
  ${bloom(48, 76, "#EDE8E2", "#B8B2A6")}
  <rect x="44" y="80" width="3" height="2" fill="#35502A"/>
  <!-- 洒水壶 -->
  <rect x="118" y="79" width="15" height="8" fill="#4A5460"/>
  <rect x="118" y="79" width="15" height="1" fill="#5E6A78"/>
  <rect x="112" y="81" width="6" height="2" fill="#4A5460"/>
  <rect x="124" y="76" width="4" height="3" fill="#39424C"/>

  <!-- 边角压暗 -->
  <rect x="0" y="0" width="4" height="${H}" fill="#000" opacity=".35"/>
  <rect x="${W - 4}" y="0" width="4" height="${H}" fill="#000" opacity=".35"/>
</svg>`;
}
