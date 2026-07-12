export default function ChatMessage({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`message${isUser ? " message-user" : " message-ai"}`}>
      <div className="message-avatar">{isUser ? "👤" : ""}</div>
      <div className="message-content">
        <div className="message-bubble">{message.content}</div>
      </div>
    </div>
  );
}
