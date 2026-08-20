/* 后端接口。/api/turn 是 POST + SSE，所以用 fetch 手动解流，不能用 EventSource。 */

async function jsonPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${path} 返回 ${res.status}`);
  }
  return res.json();
}

export async function getMeta() {
  const res = await fetch("/api/meta");
  if (!res.ok) throw new Error("拿不到链路信息，后端可能没起来");
  return res.json();
}

/* 匿名玩家标识。不是账号，不含任何个人信息 ——
   它唯一的用途是把同一个人的多局串起来，好算次日留存。
   放 localStorage 而不是 cookie：不跨站发送，清浏览器数据就等于退出。 */
const PLAYER_KEY = "alienlearn_player_id";

export function playerId() {
  let id = null;
  try {
    id = localStorage.getItem(PLAYER_KEY);
    if (!id) {
      id = (crypto.randomUUID?.() || `p${Date.now()}${Math.random().toString(16).slice(2)}`)
        .replace(/-/g, "");
      localStorage.setItem(PLAYER_KEY, id);
    }
  } catch {
    /* 隐私模式下 localStorage 会抛错。退回匿名 —— 这个人算不进留存，
       但一定不能因为拿不到 ID 就玩不了。 */
    return "anonymous";
  }
  return id;
}

export const createSession = (sceneId) =>
  jsonPost("/api/session", { scene_id: sceneId, player_id: playerId() });

export async function getMetrics() {
  const res = await fetch("/api/metrics");
  return res.ok ? res.json() : null;
}

/* 跨局累计（结算屏用）。拿不到就当没有 —— 累计是锦上添花，不能挡住结算 */
export async function getPlayerStats() {
  try {
    const res = await fetch(`/api/player/${playerId()}/stats`);
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}

/* 前端埋点，发后即忘。它本身就是用来报告前端故障的，
   所以失败绝不能反过来影响游戏 —— 吞掉所有错误。 */
export function sendClientEvent(sessionId, type, payload) {
  if (!sessionId) return;
  fetch("/api/client_event", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, type, payload }),
  }).catch(() => {});
}

/** 逐个产出后端事件：{event, data} */
export async function* streamTurn(sessionId, text) {
  const res = await fetch("/api/turn", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, text }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `传输失败（${res.status}）`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let split;
    while ((split = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7).trim();
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (!data) continue;
      try {
        yield { event, data: JSON.parse(data) };
      } catch {
        /* 半截的 JSON 直接丢掉，下一块会补上 */
      }
    }
  }
}
