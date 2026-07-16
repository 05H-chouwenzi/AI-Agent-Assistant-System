/**
 * ChatContext — 全局聊天状态管理（WebSocket 版）
 *
 * 已从 SSE 切换到 WebSocket，支持 Agent 路由轨迹 & 工具状态推送。
 */
import { createContext, useContext, useState, useRef, useCallback, useEffect } from "react";
import { getConversations, createConversation, deleteConversation, getConversationMessages } from "../api/chat";
import { connectChatWs, sendChatMessage } from "../api/ws";

function genId() {
  return Date.now() + Math.floor(Math.random() * 999999);
}

export const STATUS_STEPS = {
  rag: { icon: "📚", text: "正在从知识库检索相关内容..." },
  tool: { icon: "🔧", text: "正在调用外部工具查询数据..." },
  generating: { icon: "✍️", text: "正在生成回答..." },
  done: { icon: "✅", text: "回答完成" },
};

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [thinkingStatus, setThinkingStatus] = useState("");
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const abortRef = useRef(null);
  const bottomRef = useRef(null);
  const urlOverrideRef = useRef(false);
  const [isThinking, setIsThinking] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");

  const loadMessages = useCallback(async (convId) => {
    try {
      const data = await getConversationMessages(convId);
      setMessages(data);
    } catch { setMessages([]); }
  }, []);

  const loadConversations = useCallback(async () => {
    try {
      const data = await getConversations();
      setConversations(data);
      if (data.length > 0 && !activeId && !urlOverrideRef.current) {
        setActiveId(data[0].id);
        loadMessages(data[0].id);
      }
      urlOverrideRef.current = false;
    } catch {}
  }, [activeId, loadMessages]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) loadConversations();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const refreshConversations = useCallback(async () => {
    try { const data = await getConversations(); setConversations(data); } catch {}
  }, []);

  const selectConversation = useCallback((id) => {
    if (id === activeId) return;
    urlOverrideRef.current = true;
    setActiveId(id); setMessages([]);
    loadMessages(id);
  }, [activeId, loadMessages]);

  const clearMessages = useCallback(() => { setMessages([]); }, []);

  const newChat = useCallback(async () => {
    try {
      const conv = await createConversation("新对话");
      setConversations((prev) => [conv, ...prev]);
      urlOverrideRef.current = true;
      setActiveId(conv.id); setMessages([]);
      return conv.id;
    } catch { return null; }
  }, []);

  const removeConversation = useCallback(async (id) => {
    try { await deleteConversation(id); } catch {}
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      if (activeId === id && next.length > 0) {
        urlOverrideRef.current = true;
        setActiveId(next[0].id); loadMessages(next[0].id);
      } else if (activeId === id) { setActiveId(null); setMessages([]); }
      return next;
    });
  }, [activeId, loadMessages]);

  const send = useCallback((question) => {
    if (!activeId) { newChat().then((newId) => { if (newId) doSend(question, newId); }); return; }
    doSend(question, activeId);
  }, [activeId, newChat]);

  const doSend = useCallback((question, convId) => {
    const userMsg = { id: genId(), role: "user", content: question, time: new Date().toLocaleTimeString() };
    const aiMsgId = genId() + 1;
    const aiMsg = { id: aiMsgId, role: "assistant", content: "", time: new Date().toLocaleTimeString() };

    setMessages((prev) => [...prev, userMsg, aiMsg]);
    setLoading(true);
    setIsThinking(true);
    setStreamingContent("");

    const token = localStorage.getItem("token");
    let aiContent = "";

    // ── WebSocket 连接 ──
    const ws = connectChatWs(
      convId,
      token,
      (data) => {
        switch (data.type) {
          case "token":
            aiContent += data.content;
            setStreamingContent(aiContent);
            setMessages((prev) =>
              prev.map((m) => m.id === aiMsgId ? { ...m, content: aiContent } : m)
            );
            break;

          case "route":
            // Agent 路由轨迹 — 显示为状态提示
            setThinkingStatus(`🔄 ${data.label || data.agent || "路由中..."}`);
            break;

          

          

          

          case "title_update":
            refreshConversations();
            break;

          case "done": {
            const finalContent = data.content || aiContent;
            if (finalContent) {
              setMessages((prev) =>
                prev.map((m) => m.id === aiMsgId ? { ...m, content: finalContent } : m)
              );
            }
            setLoading(false);
            setIsThinking(false);
            setThinkingStatus("");
            setStreamingContent("");
            refreshConversations();
            break;
          }

          case "error":
            setMessages((prev) =>
              prev.map((m) => m.id === aiMsgId
                ? { ...m, content: data.content || "服务异常，请稍后重试" }
                : m
              )
            );
            setLoading(false);
            setIsThinking(false);
            setThinkingStatus("");
            setStreamingContent("");
            break;

          case "ping":
            // 心跳 — 无需处理
            break;
        }
      },
      (err) => {
        // WebSocket 连接错误
        setMessages((prev) =>
          prev.map((m) => m.id === aiMsgId
            ? { ...m, content: "连接中断，请检查网络后重试" }
            : m
          )
        );
        setLoading(false);
        setIsThinking(false);
        setThinkingStatus("");
        setStreamingContent("");
      }
    );

    // 保存 WebSocket 引用以便取消
    abortRef.current = { ws, aiMsgId };

    // 发送消息
    sendChatMessage(ws, question);
  }, [refreshConversations]);

  const cancelStream = useCallback(() => {
    if (abortRef.current?.ws) {
      abortRef.current.ws.close();
      abortRef.current = null;
    }
    setLoading(false);
    setIsThinking(false);
    setThinkingStatus("");
    setStreamingContent("");
  }, []);

  const value = {
    messages, loading, thinkingStatus, conversations, activeId, bottomRef,
    isThinking, streamingContent,
    send, cancelStream, setActiveId: selectConversation,
    newChat, deleteConversation: removeConversation, clearMessages, loadConversations,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) { throw new Error("useChat must be used within a ChatProvider"); }
  return ctx;
}
