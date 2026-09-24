import { useEffect, useRef, useState } from "react";
import FileIcon from "./FileIcon";
import {
  deleteChatAttachment,
  uploadChatAttachment,
} from "../api/chat";
import {
  MAX_ATTACHMENTS,
  MAX_ATTACHMENT_BYTES,
  SUPPORTED_ATTACHMENT_ACCEPT,
  attachmentTypeLabel,
  formatFileSize,
  isSupportedAttachment,
} from "../utils/attachments";

export default function ChatInput({ onSend, loading }) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState("");
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;

    ta.style.height = "auto";
    if (ta.scrollHeight > ta.clientHeight) {
      const newHeight = Math.min(ta.scrollHeight, 200);
      ta.style.height = `${newHeight}px`;
      ta.style.overflowY = newHeight >= 200 ? "auto" : "hidden";
    } else {
      ta.style.overflowY = "hidden";
    }
  }, [text]);

  const addFiles = async (files) => {
    const incoming = Array.from(files || []);
    if (!incoming.length) return;

    setError("");
    setUploading(true);
    let nextCount = attachments.length;

    try {
      for (const file of incoming) {
        if (!isSupportedAttachment(file)) {
          setError(`不支持的文件类型：${file.name}`);
          continue;
        }
        if (file.size > MAX_ATTACHMENT_BYTES) {
          setError(`附件过大（最大 20MB）：${file.name}`);
          continue;
        }
        if (nextCount >= MAX_ATTACHMENTS) {
          setError(`每条消息最多 ${MAX_ATTACHMENTS} 个附件`);
          break;
        }

        const attachment = await uploadChatAttachment(file);
        const previewUrl = attachment.kind === "image" ? URL.createObjectURL(file) : null;
        setAttachments((prev) => [...prev, { ...attachment, previewUrl }]);
        nextCount += 1;
      }
    } catch (err) {
      setError(err.response?.data?.detail || "附件上传失败，请重试");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const removeAttachment = (attachment) => {
    setAttachments((prev) => prev.filter((item) => item.id !== attachment.id));
    if (attachment.previewUrl) URL.revokeObjectURL(attachment.previewUrl);
    deleteChatAttachment(attachment.id).catch(() => {});
  };

  const handleSend = () => {
    if (loading || uploading) return;
    if (!text.trim() && attachments.length === 0) return;

    onSend(text.trim(), attachments);
    setText("");
    setAttachments([]);
    setError("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.overflowY = "hidden";
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handlePaste = (e) => {
    const files = Array.from(e.clipboardData?.files || []);
    const images = files.filter((file) => file.type.startsWith("image/"));
    if (images.length) {
      e.preventDefault();
      addFiles(images);
    }
  };

  const canSend = !loading && !uploading && (text.trim() || attachments.length > 0);

  return (
    <div className="chat-input-area">
      {attachments.length > 0 && (
        <div className="chat-attachments" aria-label="待发送附件">
          {attachments.map((attachment) => (
            <div className="chat-attachment-card" key={attachment.id}>
              {attachment.previewUrl ? (
                <img className="chat-attachment-thumb" src={attachment.previewUrl} alt={attachment.filename} />
              ) : (
                <span className="chat-attachment-icon">
                  <FileIcon type={attachment.extension.replace(".", "")} />
                </span>
              )}
              <div className="chat-attachment-info">
                <div className="chat-attachment-name" title={attachment.filename}>{attachment.filename}</div>
                <div className="chat-attachment-meta">
                  {attachmentTypeLabel(attachment)} · {formatFileSize(attachment.size)}
                </div>
              </div>
              <button
                type="button"
                className="chat-attachment-remove"
                onClick={() => removeAttachment(attachment)}
                aria-label={`删除附件 ${attachment.filename}`}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      <div
        className={`input-wrapper${isDragging ? " dragging" : ""}`}
        onDragEnter={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          addFiles(e.dataTransfer?.files);
        }}
      >
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder="输入你的问题，Enter 发送，Shift+Enter 换行"
          rows={1}
          cols={180}
          disabled={loading}
        />
        <div className="input-tools">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={SUPPORTED_ATTACHMENT_ACCEPT}
            style={{ display: "none" }}
            onChange={(e) => addFiles(e.target.files)}
          />
          <button
            type="button"
            className="input-tool-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={loading || uploading}
            title="添加附件"
            aria-label="添加附件"
          >
            {uploading ? <span className="spinner"></span> : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            )}
          </button>
          <button className="send-btn" onClick={handleSend} disabled={!canSend} title="发送">
            {loading ? <span className="spinner"></span> : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="chat-attachment-error" role="alert">{error}</div>
      )}
    </div>
  );
}
