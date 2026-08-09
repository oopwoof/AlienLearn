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

export const createSession = (sceneId) => jsonPost("/api/session", { scene_id: sceneId });

export async function getMetrics() {
  const res = await fetch("/api/metrics");
  return res.ok ? res.json() : null;
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
