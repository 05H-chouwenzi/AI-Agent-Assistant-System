import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { attachmentTypeLabel, formatFileSize } from "../utils/attachments";

export default function ChatMessage({ message, thinkingStatus }) {
  const isUser = message.role === "user";
  const showBubble = !thinkingStatus || message.content;
  const attachments = message.attachments || [];

  return (
    <div className={`message${isUser ? " message-user" : " message-ai"}`}>
      <div className="message-avatar">{isUser ? "👤" : "E"}</div>
      <div className="message-content">
        {isUser && attachments.length > 0 && (
          <div className="message-attachments">
            {attachments.map((attachment) => (
              <div className="chat-attachment-card" key={attachment.id}>
                {attachment.previewUrl ? (
                  <img className="chat-attachment-thumb" src={attachment.previewUrl} alt={attachment.filename} />
                ) : (
                  <div className="chat-attachment-info">
                    <div className="chat-attachment-name">{attachment.filename}</div>
                    <div className="chat-attachment-meta">
                      {attachmentTypeLabel(attachment)} · {formatFileSize(attachment.size)}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
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
