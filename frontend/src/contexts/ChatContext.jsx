/**
 * ChatContext — 全局聊天状态管理
 *
 * 将聊天状态（消息列表、SSE 流式连接、思考状态）提升到 App 级别，
 * 使得用户在页面间切换时，AI 的回复不会中断。
 *
 * 使用方式：
 *   import { useChat } from "../contexts/ChatContext";
 *   const { messages, loading, thinkingStatus, send } = useChat();
 */
import { createContext, useContext, useState, useRef, useCallback, useEffect } from "react";
import { getConversations, createConversation, deleteConversation, getConversationMessages } from "../api/chat";

const SSE_URL = `${import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? "" : "http://localhost:8000")}/api/chat/stream`;

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

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  // ========== 聊天状态 ==========
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [thinkingStatus, setThinkingStatus] = useState("");
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);

  // SSE 流的 AbortController（用于离开时取消）
  const abortRef = useRef(null);
  // 消息列表底部 ref（用于自动滚动）
  const bottomRef = useRef(null);
  // 防止 loadConversations 自动选中与 URL 参数冲突
  const urlOverrideRef = useRef(false);

  // ========== SSE 流式连接标识（供其他页面展示"思考中"提示） ==========
  const [isThinking, setIsThinking] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");

  // ========== 加载消息 & 会话列表 ==========
  const loadMessages = useCallback(async (convId) => {
    try {
      const data = await getConversationMessages(convId);
      setMessages(data);
    } catch {
      setMessages([]);
    }
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
    } catch {
      // ignore
    }
  }, []); // eslint-disable-line

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) loadConversations();
  }, []); // eslint-disable-line

  const refreshConversations = useCallback(async () => {
    try {
      const data = await getConversations();
      setConversations(data);
    } catch {
      // ignore
    }
  }, []);

  const selectConversation = useCallback((id) => {
    if (id === activeId) return;
    urlOverrideRef.current = true;
    setActiveId(id);
    setMessages([]);
    loadMessages(id);
  }, [activeId, loadMessages]);

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
      try {
        await deleteConversation(id);
      } catch {
        // ignore
      }
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
    [activeId, loadMessages]
  );

  // ========== 发送消息（核心 — SSE 流式连接） ==========
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
        time: new Date().toLocaleTimeString("zh-CN", {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };
      const aiMsgId = genId() + 1;
      const aiMsg = {
        id: aiMsgId,
        role: "assistant",
        content: "",
        time: new Date().toLocaleTimeString("zh-CN", {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };

      setMessages((prev) => [...prev, userMsg, aiMsg]);
      setLoading(true);
      setIsThinking(true);
      setStreamingContent("");

      const token = localStorage.getItem("token");
      const headers = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      // 创建 AbortController
      const controller = new AbortController();
      abortRef.current = controller;

      // ========== 流式 SSE 逐字解析（async IIFE，后台运行） ==========
      (async () => {
        try {
          const res = await fetch(SSE_URL, {
            method: "POST",
            headers,
            signal: controller.signal,
            body: JSON.stringify({ question, conversation_id: convId }),
          });
          if (!res.ok) throw new Error("HTTP " + res.status);

          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          let aiContent = "";
          let finished = false;

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
                    setStreamingContent(aiContent);
                    break;
                  case "tool_call": {
                    const toolCalls = Array.isArray(data.content)
                      ? data.content
                      : [data.content];
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === aiMsgId ? { ...m, tool_calls: toolCalls } : m
                      )
                    );
                    break;
                  }
                  case "done": {
                    const doneContent =
                      typeof data.content === "object"
                        ? data.content.content
                        : data.content;
                    if (doneContent) aiContent = doneContent;
                    setLoading(false);
                    setIsThinking(false);
                    setThinkingStatus("");
                    setStreamingContent("");
                    const newConvId =
                      typeof data.content === "object"
                        ? data.content.conversation_id
                        : null;
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
                    setIsThinking(false);
                    setThinkingStatus("");
                    setStreamingContent("");
                    finished = true;
                    break;
                }
              } catch {
                // skip
              }
            }
          };

          while (!finished) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const lines = [];
            while (buffer.includes("\n\n")) {
              const sep = buffer.indexOf("\n\n");
              lines.push(buffer.slice(0, sep));
              buffer = buffer.slice(sep + 2);
            }
            processLines(lines);
            // 批量更新消息内容
            if (aiContent) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === aiMsgId ? { ...m, content: aiContent } : m
                )
              );
            }
            // 让出主线程供 React 渲染
            if (!finished) await new Promise((r) => setTimeout(r, 0));
          }

          setLoading(false);
          setIsThinking(false);
          setThinkingStatus("");
          setStreamingContent("");
        } catch (err) {
          if (err.name === "AbortError") {
            // 用户主动取消或离开 — 不处理
            return;
          }
          setLoading(false);
          setIsThinking(false);
          setThinkingStatus("");
          setStreamingContent("");
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId
                ? { ...m, content: "抱歉，服务暂时不可用。请确认后端已启动。" }
                : m
            )
          );
        } finally {
          abortRef.current = null;
        }
      })();
    },
    [refreshConversations]
  );

  // ========== 取消正在进行的流式回复 ==========
  const cancelStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setLoading(false);
    setIsThinking(false);
    setThinkingStatus("");
    setStreamingContent("");
  }, []);

  // ========== Context 值 ==========
  const value = {
    // 聊天状态
    messages,
    loading,
    thinkingStatus,
    conversations,
    activeId,
    bottomRef,

    // 全局思考标识（其他页面可读取）
    isThinking,
    streamingContent,

    // 操作方法
    send,
    cancelStream,
    setActiveId: selectConversation,
    newChat,
    deleteConversation: removeConversation,
    clearMessages,
    loadConversations,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

/**
 * useChat — 在任意组件中读取聊天状态
 *
 * 在 ChatPage 中使用时提供完整聊天界面能力；
 * 在其他页面中使用时可读取 isThinking / thinkingStatus 来展示"AI 正在思考"指示器。
 */
export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) {
    throw new Error("useChat must be used within a ChatProvider");
  }
  return ctx;
}
