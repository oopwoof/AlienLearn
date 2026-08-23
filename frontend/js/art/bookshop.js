/* 像素箱庭 · 深夜旧书店（160 × 90 逻辑像素，手写 rect）。
   与前两个场景共享 NPC 头部几何（faces.js），只换发型、衣着和环境。
   调色板：深夜蓝的屋子 + 柜台一盏台灯的暖黄。全场只有一处亮 ——
   拉面馆是满屋暖橙，花店是暮色紫加花的亮色，这里刻意只留一个光源，
   因为这一局的戏在那盏灯照到的那本书上。 */

import { FACES } from "./faces.js";

const W = 160;
const H = 90;

/* 一格书：竖着的深浅色条。逐本画 rect 比任何取巧都像书架 */
function books(x, y, h, spec) {
  let cx = x;
  return spec
    .map(([w, fill]) => {
      const r = `<rect x="${cx}" y="${y + (h - h)}" width="${w}" height="${h}" fill="${fill}"/>`;
      cx += w;
      return r;
    })
    .join("");
}

/* 斜靠的一本：书架边总有没插回去的 */
function leaning(x, y, fill) {
  return `
    <rect x="${x}" y="${y + 2}" width="4" height="9" fill="${fill}"/>
    <rect x="${x}" y="${y + 2}" width="4" height="1" fill="#000" opacity=".25"/>`;
}

/* 灯下的浮尘：复用花店雾气的上升动画 */
function dust() {
  return [0, 0.9, 1.7, 2.4]
    .map((d, i) => `<rect class="puff" style="animation-delay:${d}s" x="${64 + i * 7}" y="40" width="2" height="2" fill="#E8C05A" opacity="0"/>`)
    .join("");
}

/* 窗外运河的反光：慢慢闪的几点 */
function canal() {
  return [[10, 40], [19, 42], [30, 41], [38, 43]]
    .map(([x, y], i) => `<rect class="glow" style="animation-delay:${(i * 0.6).toFixed(1)}s" x="${x}" y="${y}" width="3" height="1" fill="#7FA8C8" opacity=".5"/>`)
    .join("");
}

export function bookshopArt() {
  return `
<svg viewBox="0 0 ${W} ${H}" shape-rendering="crispEdges" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
  <!-- 底：深夜蓝 -->
  <rect x="0" y="0" width="${W}" height="${H}" fill="#0F1219"/>
  <rect x="0" y="10" width="${W}" height="50" fill="#1A202B"/>
  <rect x="0" y="10" width="${W}" height="2" fill="#232B38"/>

  <!-- 台灯的光锥：全场唯一的暖色，落在柜台上 -->
  <rect x="60" y="12" width="44" height="48" fill="#E8C05A" opacity=".06"/>
  <rect x="66" y="30" width="32" height="30" fill="#E8C05A" opacity=".05"/>

  <!-- 左窗：外面是运河。对岸的灯在水面碎成几点 -->
  <rect x="4" y="16" width="44" height="32" fill="#141922"/>
  <rect x="6" y="18" width="40" height="28" fill="#1C2A3A"/>
  <rect x="6" y="18" width="40" height="12" fill="#16202C"/>
  <rect x="9" y="22" width="2" height="2" fill="#C8B888" opacity=".6"/>
  <rect x="21" y="20" width="2" height="3" fill="#C8B888" opacity=".45"/>
  <rect x="35" y="23" width="2" height="2" fill="#C8B888" opacity=".5"/>
  <rect x="6" y="38" width="40" height="8" fill="#16222E"/>
  ${canal()}
  <rect x="25" y="18" width="2" height="28" fill="#141922"/>
  <rect x="6" y="31" width="40" height="1" fill="#141922"/>

  <!-- 天花板 -->
  <rect x="0" y="0" width="${W}" height="10" fill="#0C0F15"/>

  <!-- 左墙书架：从地板堆到窗沿，塞得满满当当 -->
  <rect x="0" y="50" width="52" height="2" fill="#4A3826"/>
  ${books(0, 52, 8, [[3, "#5A3A32"], [2, "#3E4A38"], [4, "#7A6242"], [2, "#2E3A4A"], [3, "#6A4A3A"], [2, "#4A4438"], [4, "#3A3242"], [3, "#5E4632"], [2, "#42503E"], [3, "#6E5A3E"]])}
  ${leaning(31, 52, "#8A6B42")}

  <!-- 后墙书架：三层，暗处只剩轮廓 -->
  <rect x="108" y="20" width="52" height="2" fill="#4A3826"/>
  <rect x="108" y="36" width="52" height="2" fill="#4A3826"/>
  <rect x="108" y="52" width="52" height="2" fill="#4A3826"/>
  ${books(110, 12, 8, [[3, "#39424C"], [2, "#4A3A32"], [4, "#3E4438"], [2, "#33404A"], [3, "#4A4030"], [2, "#3A3444"], [4, "#443A2E"], [3, "#38424A"], [2, "#4A3E34"]])}
  ${books(110, 28, 8, [[4, "#3E3444"], [2, "#4A4034"], [3, "#37424C"], [3, "#4A3830"], [2, "#3E4A3A"], [4, "#443C2E"], [2, "#39424C"], [3, "#4A3E34"]])}
  ${books(112, 44, 8, [[3, "#4A3E34"], [2, "#37424C"], [4, "#3E4438"], [2, "#4A3830"], [3, "#3A3444"], [3, "#443C2E"]])}
  ${leaning(140, 44, "#5A4632")}

  <!-- 挂钟：快十一点了。指针位置就是这一局的时间压力 -->
  <rect x="72" y="14" width="14" height="14" fill="#2A2118"/>
  <rect x="74" y="16" width="10" height="10" fill="#C9BEAA"/>
  <rect x="78" y="18" width="1" height="4" fill="#2A2118"/>
  <rect x="79" y="21" width="3" height="1" fill="#2A2118"/>

  <!-- 台灯：绿玻璃罩，全场唯一光源 -->
  <rect x="118" y="40" width="2" height="14" fill="#4A4438"/>
  <rect x="112" y="36" width="14" height="5" fill="#2E4A38"/>
  <rect x="112" y="36" width="14" height="1" fill="#3E6048"/>
  <rect class="flicker" x="115" y="41" width="8" height="2" fill="#FFE9B8"/>
  <rect class="glow" x="106" y="38" width="26" height="16" fill="#E8C05A" opacity=".16"/>

  <!-- 灯下的浮尘 -->
  ${dust()}

  <!-- Idris：灰白短发，深蓝开衫 + 洗旧的衬衫。头部网格与前两场景完全一致 -->
  <g class="js-boss boss">
    <rect x="76" y="45" width="7" height="15" fill="#2E3A4E"/>
    <rect x="117" y="45" width="7" height="15" fill="#2E3A4E"/>
    <rect x="76" y="56" width="7" height="4" fill="#B8865C"/>
    <rect x="117" y="56" width="7" height="4" fill="#B8865C"/>
    <rect x="82" y="43" width="36" height="17" fill="#2E3A4E"/>
    <rect x="88" y="43" width="24" height="17" fill="#8A8F98"/>
    <rect x="94" y="43" width="2" height="17" fill="#6E747E"/>
    <rect x="105" y="43" width="2" height="17" fill="#6E747E"/>
    <rect x="99" y="46" width="2" height="8" fill="#5E646E"/>
    <rect x="86" y="40" width="28" height="3" fill="#A8ADB6"/>
    <rect x="96" y="38" width="8" height="3" fill="#A87548"/>
    <rect x="91" y="23" width="18" height="16" fill="#C89468"/>
    <rect x="91" y="23" width="2" height="16" fill="#A87548"/>
    <rect x="89" y="24" width="2" height="8" fill="#B2AB9E"/>
    <rect x="109" y="24" width="2" height="8" fill="#B2AB9E"/>
    <rect x="90" y="17" width="20" height="6" fill="#B2AB9E"/>
    <rect x="90" y="17" width="20" height="2" fill="#C6BFB4"/>
    <rect x="88" y="20" width="2" height="4" fill="#B2AB9E"/>
    <rect x="110" y="20" width="2" height="4" fill="#B2AB9E"/>
    <g class="js-face">${FACES.tired}</g>
  </g>

  <!-- 柜台：深色木头，被无数本书磨亮了边 -->
  <rect x="0" y="60" width="${W}" height="5" fill="#5E4A32"/>
  <rect x="0" y="60" width="${W}" height="1" fill="#7A6242"/>
  <rect x="0" y="64" width="${W}" height="1" fill="#332A1E"/>
  <rect x="0" y="65" width="${W}" height="8" fill="#3E3426"/>
  <rect x="0" y="70" width="${W}" height="3" fill="#2A2418"/>
  <rect x="42" y="65" width="1" height="5" fill="#332A1E"/>
  <rect x="108" y="65" width="1" height="5" fill="#332A1E"/>

  <!-- 柜台后那一格：那本不卖的书。刻意单独一格、单独一本、正对灯光 -->
  <rect x="128" y="55" width="16" height="6" fill="#241E16"/>
  <rect x="129" y="56" width="14" height="4" fill="#1A150F"/>
  <rect x="134" y="55" width="4" height="6" fill="#7A2834"/>
  <rect x="134" y="55" width="4" height="1" fill="#A83A48"/>
  <rect x="135" y="57" width="2" height="1" fill="#E8C05A" opacity=".7"/>

  <!-- 柜台上：摊开的一本 + 一摞待上架 -->
  <rect x="60" y="56" width="20" height="4" fill="#C9BEAA"/>
  <rect x="60" y="56" width="20" height="1" fill="#DED2BE"/>
  <rect x="69" y="56" width="2" height="4" fill="#A89E8A"/>
  <rect x="30" y="57" width="14" height="3" fill="#4A3E34"/>
  <rect x="31" y="54" width="14" height="3" fill="#3E4438"/>
  <rect x="30" y="51" width="13" height="3" fill="#5A3A32"/>

  <!-- 前景：柜台外侧的暗 -->
  <rect x="0" y="73" width="${W}" height="17" fill="#0D1016"/>
  <rect x="18" y="78" width="24" height="6" fill="#4A3E34"/>
  <rect x="18" y="78" width="24" height="1" fill="#5E5040"/>
  <rect x="22" y="76" width="20" height="2" fill="#3E4438"/>
  <rect x="118" y="79" width="18" height="5" fill="#C9BEAA"/>
  <rect x="118" y="79" width="18" height="1" fill="#DED2BE"/>
  <rect x="126" y="79" width="2" height="5" fill="#A89E8A"/>

  <!-- 边角压暗：夜里的店只有中间是亮的 -->
  <rect x="0" y="0" width="6" height="${H}" fill="#000" opacity=".4"/>
  <rect x="${W - 6}" y="0" width="6" height="${H}" fill="#000" opacity=".4"/>
  <rect x="0" y="0" width="${W}" height="4" fill="#000" opacity=".3"/>
</svg>`;
}
