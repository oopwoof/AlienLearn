/* NPC 的六套表情。头部几何是场景无关的约定：
   脸框 x91-109 / y24-39，眉 y28、眼 y30、嘴 y34 ——
   新场景的 NPC 保持同一头部网格，表情就能直接共享，这是最大的一块美术资产。 */

export const FACES = {
  warm: `
    <rect class="ink" x="94" y="28" width="5" height="1"/>
    <rect class="ink" x="102" y="28" width="5" height="1"/>
    <rect class="ink" x="95" y="30" width="2" height="2"/>
    <rect class="ink" x="104" y="30" width="2" height="2"/>
    <rect class="ink" x="97" y="34" width="6" height="1"/>`,
  annoyed: `
    <rect class="ink" x="94" y="27" width="3" height="1"/>
    <rect class="ink" x="97" y="28" width="2" height="1"/>
    <rect class="ink" x="102" y="28" width="2" height="1"/>
    <rect class="ink" x="104" y="27" width="3" height="1"/>
    <rect class="ink" x="95" y="30" width="2" height="2"/>
    <rect class="ink" x="104" y="30" width="2" height="2"/>
    <rect class="ink" x="97" y="34" width="6" height="1"/>
    <rect class="ink" x="98" y="35" width="4" height="1"/>`,
  suspicious: `
    <rect class="ink" x="94" y="26" width="5" height="1"/>
    <rect class="ink" x="102" y="28" width="5" height="1"/>
    <rect class="ink" x="95" y="30" width="3" height="1"/>
    <rect class="ink" x="103" y="30" width="3" height="1"/>
    <rect class="ink" x="98" y="34" width="4" height="1"/>`,
  conspiratorial: `
    <rect class="ink" x="94" y="27" width="5" height="1"/>
    <rect class="ink" x="102" y="27" width="5" height="1"/>
    <rect class="ink" x="95" y="30" width="3" height="1"/>
    <rect class="ink" x="103" y="30" width="3" height="1"/>
    <rect class="ink" x="96" y="34" width="8" height="1"/>`,
  amused: `
    <rect class="ink" x="94" y="27" width="5" height="1"/>
    <rect class="ink" x="102" y="27" width="5" height="1"/>
    <rect class="ink" x="95" y="30" width="2" height="2"/>
    <rect class="ink" x="104" y="30" width="2" height="2"/>
    <rect class="ink" x="97" y="33" width="7" height="2"/>
    <rect class="dim" x="98" y="35" width="5" height="1"/>`,
  tired: `
    <rect class="ink" x="94" y="28" width="5" height="1"/>
    <rect class="ink" x="102" y="28" width="5" height="1"/>
    <rect class="ink" x="95" y="31" width="3" height="1"/>
    <rect class="ink" x="103" y="31" width="3" height="1"/>
    <rect class="ink" x="98" y="34" width="4" height="1"/>`,
};
