import { useState, useRef, useEffect, useCallback } from "react";
import { getConversations, createConversation, deleteConversation, getConversationMessages } from "../api/chat";

const SSE_URL = `${import.meta.env.VITE_API_BASE_URL || "http://localhost:8004"}/api/chat/stream`;

function genId() {
  return Date.now() + Math.floor(Math.random() * 999999);
}

/**
 * AI 思考步骤的状态序列（带图标和文字）
 * 用于流式加载时展示当前 AI 正在做什么
 */
export const STATUS_STEPS = {
  rag: { icon: "📚", text: "正在从知识库检索相关内容..." },
  tool: { icon: "🔧", text: "正在调用外部工具查询数据..." },
  generating: { icon: "✍️", text: "正在生成回答..." },
  done: { icon: "✅", text: "回答完成" },
};

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  /** 当前 AI 思考状态文字（如 "📚 正在从知识库检索..."） */
  const [thinkingStatus, setThinkingStatus] = useState("");
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const bottomRef = useRef(null);

  // 防止 loadConversations 自动选中与 URL 参数冲突
  const urlOverrideRef = useRef(false);

  const loadMessages = async (convId) => {
    try {
      const data = await getConversationMessages(convId);
      setMessages(data);
    } catch {
      setMessages([]);
    }
  };

  const loadConversations = useCallback(async () => {
    try {
      const data = await getConversations();
      setConversations(data);
      if (data.length > 0 && !activeId && !urlOverrideRef.current) {
        setActiveId(data[0].id);
        loadMessages(data[0].id);
      }
      urlOverrideRef.current = false;
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) loadConversations();
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      const data = await getConversations();
      setConversations(data);
    } catch { /* noop */ }
  }, []);

  const selectConversation = useCallback((id) => {
    if (id === activeId) return;
    urlOverrideRef.current = true;
    setActiveId(id);
    loadMessages(id);
  }, [activeId]);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  const newChat = useCallback(async () => {
    try {
      const conv = await createConversation("新对话");
      setConversations((prev) => [conv, ...prev]);
      urlOverrideRef.current = true;
      setActiveId(conv.id);
      setMessages([]);
      return conv.id;
    } catch {
      return null;
    }
  }, []);

  const removeConversation = useCallback(
    async (id) => {
      try { await deleteConversation(id); } catch { /* noop */ }
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id);
        if (activeId === id && next.length > 0) {
          urlOverrideRef.current = true;
          setActiveId(next[0].id);
          loadMessages(next[0].id);
        } else if (activeId === id) {
          setActiveId(null);
          setMessages([]);
        }
        return next;
      });
    },
    [activeId]
  );

  const send = useCallback(
    (question) => {
      if (!activeId) {
        newChat().then((newId) => {
          if (newId) doSend(question, newId);
        });
        return;
      }
      doSend(question, activeId);
    },
    [activeId, newChat]
  );

  const doSend = useCallback(
    (question, convId) => {
      const userMsg = {
        id: genId(),
        role: "user",
        content: question,
        time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
      };
      const aiMsgId = genId() + 1;
      const aiMsg = {
        id: aiMsgId,
        role: "assistant",
        content: "",
        time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, userMsg, aiMsg]);
      setLoading(true);

      const token = localStorage.getItem("token");
      const headers = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      // ========== 流式 SSE 逐字解析 ==========
      // 用 async/await + setTimeout(0) 在每个 chunk 后让 React 渲染
      (async () => {
        try {
          const res = await fetch(SSE_URL, {
            method: "POST",
            headers,
            body: JSON.stringify({ question, conversation_id: convId }),
          });
          if (!res.ok) throw new Error("HTTP " + res.status);

          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          let aiContent = "";
          let finished = false;

          /** 处理一个完整的 SSE 事件行 —— 不返回，直接更新状态 */
          const processLines = (lines) => {
            for (const line of lines) {
              if (finished) break;
              if (!line.startsWith("data: ")) continue;
              try {
                const data = JSON.parse(line.slice(6));
                switch (data.type) {
                  case "status":
                    setThinkingStatus(data.content);
                    break;
                  case "chunk":
                    aiContent += data.content;
                    break;
                  case "tool_call": {
                    const toolCalls = Array.isArray(data.content) ? data.content : [data.content];
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === aiMsgId ? { ...m, tool_calls: toolCalls } : m
                      )
                    );
                    break;
                  }
                  case "done": {
                    const doneContent = typeof data.content === "object" ? data.content.content : data.content;
                    if (doneContent) aiContent = doneContent;
                    setLoading(false);
                    setThinkingStatus("");
                    const newConvId = typeof data.content === "object" ? data.content.conversation_id : null;
                    if (newConvId && newConvId !== convId) {
                      urlOverrideRef.current = true;
                      setActiveId(newConvId);
                    }
                    refreshConversations();
                    finished = true;
                    break;
                  }
                  case "error":
                    aiContent = data.content;
                    setLoading(false);
                    setThinkingStatus("");
                    finished = true;
                    break;
                }
              } catch { /* skip */ }
            }
          };

          while (!finished) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            // 批量提取所有完整的 SSE 事件
            const lines = [];
            while (buffer.includes("\n\n")) {
              const sep = buffer.indexOf("\n\n");
              lines.push(buffer.slice(0, sep));
              buffer = buffer.slice(sep + 2);
            }
            processLines(lines);
            // 批量更新一次 UI
            if (aiContent) {
              setMessages((prev) =>
                prev.map((m) => (m.id === aiMsgId ? { ...m, content: aiContent } : m))
              );
            }
            // 屈服给 React 渲染
            if (!finished) await new Promise((r) => setTimeout(r, 0));
          }

          setLoading(false);
          setThinkingStatus("");
        } catch (err) {
          setLoading(false);
          setThinkingStatus("");
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId
                ? { ...m, content: "抱歉，服务暂时不可用。请确认后端已启动。" }
                : m
            )
          );
        }
      })();
    },
    [refreshConversations]
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return {
    messages, loading, thinkingStatus, send, bottomRef,
    conversations, activeId, setActiveId: selectConversation,
    newChat, deleteConversation: removeConversation, clearMessages,
    loadConversations,
  };
}
