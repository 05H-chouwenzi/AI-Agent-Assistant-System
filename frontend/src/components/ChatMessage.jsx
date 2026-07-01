import { useNavigate } from "react-router-dom";

export default function ChatMessage({ message }) {
  const isUser = message.role === "user";
  const navigate = useNavigate();
  const toolCalls = message.tool_calls;

  return (
    <div className={`message${isUser ? " message-user" : " message-ai"}`}>
      <div className="message-avatar">{isUser ? "👤" : ""}</div>
      <div className="message-content">
        <div className="message-bubble">{message.content}</div>
        {toolCalls && toolCalls.length > 0 && (
          <div className="message-tool-bar">
            {toolCalls.map((tc, i) => (
              <span
                key={i}
                className="tool-call-chip"
                onClick={() => navigate(`/tools?tool=${tc.tool_name || tc.name || ""}`)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && navigate(`/tools?tool=${tc.tool_name || tc.name || ""}`)}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                </svg>
                {tc.tool_name || tc.name || "工具调用"}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
