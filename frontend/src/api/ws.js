/**
 * WebSocket 聊天客户端
 * 替代 SSE，支持 Agent 路由轨迹 & 工具状态推送
 */

const WS_BASE = import.meta.env.VITE_WS_URL || "ws://localhost:8000";

/**
 * 连接 WebSocket 聊天
 * @param {number} conversationId
 * @param {string} token
 * @param {function} onMessage - 收到消息的回调
 * @param {function} onError - 错误回调
 * @returns {WebSocket}
 */
export function connectChatWs(conversationId, token, onMessage, onError) {
  const ws = new WebSocket(
    `${WS_BASE}/api/ws/chat/${conversationId}?token=${encodeURIComponent(token)}`
  );

  ws.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data));
    } catch {
      /* ignore parse errors */
    }
  };

  ws.onerror = (e) => onError?.(e);

  return ws;
}

/**
 * 发送聊天消息
 * @param {WebSocket} ws
 * @param {string} message
 */
export function sendChatMessage(ws, message) {
  const payload = JSON.stringify({ message });
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(payload);
  } else if (ws.readyState === WebSocket.CONNECTING) {
    // WebSocket 还在连接中，等 open 后再发
    ws.addEventListener('open', () => ws.send(payload), { once: true });
  }
}

/**
 * Agent 颜色映射（前端展示用）
 */
export const AGENT_COLORS = {
  research: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  data: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  general: "text-sky-400 bg-sky-500/10 border-sky-500/20",
  synthesize: "text-amber-400 bg-amber-500/10 border-amber-500/20",
};

export const AGENT_LABELS = {
  research: "Research",
  data: "Data",
  general: "General",
  synthesize: "Synthesizer",
};
