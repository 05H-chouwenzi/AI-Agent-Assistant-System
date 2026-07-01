import "./ConfirmDialog.css";

export default function ConfirmDialog({ open, title, message, onCancel, onConfirm }) {
  if (!open) return null;

  return (
    <div className="confirm-overlay" onClick={onCancel}>
      <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-header">{title}</div>
        <div className="confirm-body">{message}</div>
        <div className="confirm-actions">
          <button className="confirm-btn cancel" onClick={onCancel}>取消</button>
          <button className="confirm-btn delete" onClick={onConfirm}>删除</button>
        </div>
      </div>
    </div>
  );
}
