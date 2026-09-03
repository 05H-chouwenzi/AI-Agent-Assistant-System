import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function ChatMessage({ message, thinkingStatus }) {
  const isUser = message.role === "user";
  const showBubble = !thinkingStatus || message.content;

  return (
    <div className={`message${isUser ? " message-user" : " message-ai"}`}>
      <div className="message-avatar">{isUser ? "👤" : ""}</div>
      <div className="message-content">
        {!isUser && thinkingStatus && (
          <div className="thinking-status">
            <span className="thinking-dots">
              <span className="dot" /><span className="dot" /><span className="dot" />
            </span>
            <span className="thinking-text">{thinkingStatus}</span>
          </div>
        )}
        {showBubble && (
          <div className="message-bubble">
            {isUser ? message.content : (
              <div className="message-markdown">
                <Markdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </Markdown>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
