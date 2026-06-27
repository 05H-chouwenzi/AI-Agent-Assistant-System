import { useState, useRef, useEffect, useCallback } from "react";
import { getConversations, createConversation, deleteConversation, getConversationMessages } from "../api/chat";

const SSE_URL = "http://localhost:8000/api/chat/stream";

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const bottomRef = useRef(null);
  const [accumulatingContent, setAccumulatingContent] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) loadConversations();
  }, []);

  const loadMessages = async (convId) => {
    try {
      const data = await getConversationMessages(convId);
      setMessages(data);
    } catch {
      setMessages([]);
    }
  };

  const loadConversations = async () => {
    try {
      const data = await getConversations();
      if (data.length > 0) {
        setConversations(data);
        setActiveId(data[0].id);
        loadMessages(data[0].id);
      } else {
        const conv = await createConversation("新对话");
        setConversations([conv]);
        setActiveId(conv.id);
      }
    } catch {
      // 不创建回退，保持空
    }
  };

  const selectConversation = useCallback((id) => {
    setActiveId(id);
    loadMessages(id);
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setAccumulatingContent("");
  }, []);

  const newChat = useCallback(async () => {
    try {
      const conv = await createConversation("新对话");
      setConversations((prev) => [conv, ...prev]);
      setActiveId(conv.id);
      setMessages([]);
    } catch {
      // 不创建回退
    }
  }, []);

  const removeConversation = useCallback(
    async (id) => {
      try { await deleteConversation(id); } catch { /* noop */ }
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id);
        if (activeId === id && next.length > 0) {
          setActiveId(next[0].id);
          loadMessages(next[0].id);
        }
        return next;
      });
    },
    [activeId]
  );

  const send = useCallback(
    (question) => {
      // 无活跃会话时自动建
      if (!activeId) {
        newChat();
        return;
      }

      const userMsg = {
        id: Date.now() + Math.random(),
        role: "user",
        content: question,
        time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);
      setAccumulatingContent("");

      const aiMsgId = Date.now() + Math.random() + 1;
      const aiMsg = {
        id: aiMsgId,
        role: "assistant",
        content: "",
        time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, aiMsg]);

      const token = localStorage.getItem("token");
      const headers = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      fetch(SSE_URL, {
        method: "POST",
        headers,
        body: JSON.stringify({ question, conversation_id: activeId }),
      })
        .then((res) => {
          if (!res.ok) throw new Error("HTTP " + res.status);
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          function pump() {
            reader.read().then(({ done, value }) => {
              if (done) { setLoading(false); return; }
              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split("\n\n");
              buffer = lines.pop() || "";
              for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                try {
                  const data = JSON.parse(line.slice(6));
                  if (data.type === "chunk") {
                    setAccumulatingContent((prev) => {
                      const next = prev + data.content;
                      setMessages((msgs) =>
                        msgs.map((m) => m.id === aiMsgId ? { ...m, content: next } : m)
                      );
                      return next;
                    });
                  }
                  if (data.type === "done") {
                    setLoading(false);
                    setAccumulatingContent(data.content);
                    setMessages((msgs) =>
                      msgs.map((m) => m.id === aiMsgId ? { ...m, content: data.content } : m)
                    );
                    if (data.conversation_id && data.conversation_id !== activeId) {
                      setActiveId(data.conversation_id);
                    }
                    // 刷新会话列表
                    loadConversations();
                  }
                } catch { /* skip */ }
              }
              pump();
            }).catch(() => setLoading(false));
          }
          pump();
        })
        .catch(() => {
          setLoading(false);
          setMessages((msgs) =>
            msgs.map((m) =>
              m.id === aiMsgId
                ? { ...m, content: "抱歉，服务暂时不可用。请确认后端已启动。" }
                : m
            )
          );
        });
    },
    [activeId, newChat]
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, accumulatingContent]);

  return {
    messages, loading, send, bottomRef,
    conversations, activeId, setActiveId: selectConversation,
    newChat, deleteConversation: removeConversation, clearMessages,
  };
}
