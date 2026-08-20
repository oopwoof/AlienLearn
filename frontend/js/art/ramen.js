/* 像素箱庭 · 雨夜拉面馆（160 × 90 逻辑像素，手写 rect）。
   场景会被克隆成红/青两个通道层，所以只能用 class 不能用 id。 */

import { FACES } from "./faces.js";

const W = 160;
const H = 90;

function lantern(x, delay) {
  return `
    <rect x="${x}" y="0" width="1" height="9" fill="#2A2118"/>
    <rect class="glow" style="animation-delay:${delay}s" x="${x - 11}" y="6" width="23" height="16" fill="#E8873A" opacity=".16"/>
    <rect x="${x - 6}" y="9" width="13" height="11" fill="#E8873A"/>
    <rect x="${x - 6}" y="9" width="13" height="1" fill="#8A4520"/>
    <rect x="${x - 6}" y="19" width="13" height="1" fill="#8A4520"/>
    <rect class="flicker" style="animation-delay:${delay}s" x="${x - 3}" y="11" width="7" height="7" fill="#FFD98A"/>`;
}

function rain() {
  const streaks = [
    [13, 20], [18, 24], [24, 21], [29, 27], [34, 22], [40, 25],
    [16, 31], [22, 34], [28, 30], [36, 33], [43, 29], [11, 27],
  ];
  return streaks
    .map(([x, y], i) => `<rect class="drop" style="animation-delay:${(i * 0.11).toFixed(2)}s" x="${x}" y="${y + 1}" width="1" height="5" fill="#5A6E99"/>`)
    .join("");
}

function steam() {
  return [0, 0.5, 1.0, 1.5, 2.0]
    .map((d, i) => `<rect class="puff" style="animation-delay:${d}s" x="${52 + (i % 3) * 4}" y="40" width="3" height="4" fill="#E8E4F0" opacity="0"/>`)
    .join("");
}

export function ramenArt() {
  return `
<svg viewBox="0 0 ${W} ${H}" shape-rendering="crispEdges" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
  <!-- 底 -->
  <rect x="0" y="0" width="${W}" height="${H}" fill="#14101F"/>
  <!-- 后墙 -->
  <rect x="0" y="10" width="${W}" height="50" fill="#2B2118"/>
  <rect x="0" y="10" width="${W}" height="2" fill="#3B2C1E"/>
  <!-- 灯笼暖光在墙上的落点 -->
  <rect x="0" y="12" width="${W}" height="22" fill="#E8873A" opacity=".07"/>

  <!-- 窗（外面在下雨） -->
  <rect x="6" y="18" width="44" height="30" fill="#1E1710"/>
  <rect x="8" y="20" width="40" height="26" fill="#0D111E"/>
  ${rain()}
  <rect x="27" y="20" width="2" height="26" fill="#1E1710"/>
  <rect x="8" y="32" width="40" height="1" fill="#1E1710"/>

  <!-- 右墙：菜单短册（压暗，不许抢主体） + 酒瓶架 -->
  <rect x="126" y="20" width="7" height="17" fill="#C9BEAA" opacity=".5"/>
  <rect x="128" y="23" width="4" height="1" fill="#8A3830" opacity=".7"/>
  <rect x="128" y="27" width="4" height="1" fill="#3A2E20" opacity=".7"/>
  <rect x="128" y="31" width="4" height="1" fill="#3A2E20" opacity=".7"/>
  <rect x="136" y="20" width="7" height="17" fill="#C9BEAA" opacity=".36"/>
  <rect x="138" y="24" width="4" height="1" fill="#3A2E20" opacity=".7"/>
  <rect x="138" y="29" width="4" height="1" fill="#3A2E20" opacity=".7"/>
  <rect x="146" y="34" width="13" height="2" fill="#1F170F"/>
  <rect x="147" y="27" width="4" height="7" fill="#6B4A2A"/>
  <rect x="153" y="25" width="4" height="9" fill="#40563A"/>

  <!-- 暖锅 + 蒸汽 -->
  <rect x="44" y="42" width="26" height="2" fill="#5C5C68"/>
  <rect x="46" y="44" width="22" height="16" fill="#3E3E48"/>
  <rect x="46" y="44" width="22" height="2" fill="#4E4E58"/>
  ${steam()}

  <!-- 老板：深色的鬓角把脸框住，剪影才读得出是个人 -->
  <g class="js-boss boss">
    <rect x="76" y="45" width="7" height="15" fill="#2E3A48"/>
    <rect x="117" y="45" width="7" height="15" fill="#2E3A48"/>
    <rect x="76" y="56" width="7" height="4" fill="#B8865C"/>
    <rect x="117" y="56" width="7" height="4" fill="#B8865C"/>
    <rect x="82" y="43" width="36" height="17" fill="#3A4656"/>
    <rect x="94" y="43" width="2" height="17" fill="#2E3A48"/>
    <rect x="105" y="43" width="2" height="17" fill="#2E3A48"/>
    <rect x="86" y="40" width="28" height="3" fill="#E8DCC8"/>
    <rect x="96" y="38" width="8" height="3" fill="#A87548"/>
    <rect x="91" y="23" width="18" height="16" fill="#C89468"/>
    <rect x="91" y="23" width="2" height="16" fill="#A87548"/>
    <rect x="89" y="24" width="2" height="9" fill="#1B1410"/>
    <rect x="109" y="24" width="2" height="9" fill="#1B1410"/>
    <rect x="90" y="16" width="20" height="7" fill="#1B1410"/>
    <rect x="89" y="21" width="22" height="2" fill="#DED2BE"/>
    <rect x="94" y="21" width="3" height="1" fill="#A83228"/>
    <rect x="104" y="21" width="3" height="1" fill="#A83228"/>
    <g class="js-face">${FACES.tired}</g>
  </g>

  <!-- 暖帘（从天花板垂下来） -->
  <rect x="0" y="10" width="${W}" height="7" fill="#A83228"/>
  <rect x="0" y="16" width="${W}" height="1" fill="#7A2018"/>
  <rect x="38" y="10" width="2" height="7" fill="#14101F"/>
  <rect x="78" y="10" width="2" height="7" fill="#14101F"/>
  <rect x="118" y="10" width="2" height="7" fill="#14101F"/>
  <rect x="0" y="0" width="${W}" height="10" fill="#1A1420"/>
  ${lantern(24, 0)}
  ${lantern(80, 0.9)}
  ${lantern(136, 1.7)}

  <!-- 吧台 -->
  <rect x="0" y="60" width="${W}" height="5" fill="#8A6238"/>
  <rect x="0" y="60" width="${W}" height="1" fill="#A87A48"/>
  <rect x="0" y="64" width="${W}" height="1" fill="#4A3320"/>
  <rect x="0" y="65" width="${W}" height="8" fill="#5B3F27"/>
  <rect x="0" y="70" width="${W}" height="3" fill="#412D1C"/>
  <rect x="30" y="65" width="1" height="5" fill="#4A3320"/>
  <rect x="96" y="65" width="1" height="5" fill="#4A3320"/>
  <!-- 老板正在装的那一碗 -->
  <rect x="126" y="55" width="24" height="2" fill="#A83228"/>
  <rect x="127" y="57" width="22" height="3" fill="#C87A32"/>

  <!-- 客人侧（前景）。离镜头最近所以最大，但在吧台沿下方，压暗、不许抢主体 -->
  <rect x="0" y="73" width="${W}" height="17" fill="#16111C"/>
  <rect x="16" y="75" width="44" height="2" fill="#5E2A24"/>
  <rect x="18" y="77" width="40" height="3" fill="#7A5228"/>
  <rect x="17" y="80" width="42" height="7" fill="#8C8478"/>
  <rect x="17" y="80" width="42" height="1" fill="#A39A8C"/>
  <rect x="20" y="86" width="36" height="2" fill="#5E594F"/>
  <rect x="76" y="80" width="30" height="1" fill="#7A6A50"/>
  <rect x="76" y="83" width="30" height="1" fill="#7A6A50"/>
  <rect x="86" y="79" width="7" height="6" fill="#332314"/>
  <rect x="118" y="79" width="13" height="9" fill="#2A323E"/>
  <rect x="118" y="79" width="13" height="1" fill="#3E4A5C"/>

  <!-- 边角压暗 -->
  <rect x="0" y="0" width="4" height="${H}" fill="#000" opacity=".35"/>
  <rect x="${W - 4}" y="0" width="4" height="${H}" fill="#000" opacity=".35"/>
</svg>`;
}
