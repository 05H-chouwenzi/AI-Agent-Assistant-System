export const SUPPORTED_ATTACHMENT_EXTENSIONS = [
  ".pdf", ".docx", ".pptx",
  ".xlsx", ".xls", ".csv",
  ".jpg", ".jpeg", ".png", ".webp",
  ".txt", ".md", ".json", ".xml",
];

export const SUPPORTED_ATTACHMENT_ACCEPT = SUPPORTED_ATTACHMENT_EXTENSIONS.join(",");
export const MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024;
export const MAX_ATTACHMENTS = 5;

export function getExtension(filename) {
  const index = filename.lastIndexOf(".");
  return index >= 0 ? filename.slice(index).toLowerCase() : "";
}

export function isSupportedAttachment(file) {
  return SUPPORTED_ATTACHMENT_EXTENSIONS.includes(getExtension(file.name));
}

export function formatFileSize(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function attachmentTypeLabel(attachment) {
  const extension = attachment.extension || getExtension(attachment.filename || "");
  const labels = {
    ".pdf": "PDF",
    ".docx": "DOCX",
    ".pptx": "PPTX",
    ".xlsx": "XLSX",
    ".xls": "XLS",
    ".csv": "CSV",
    ".jpg": "JPG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
    ".txt": "TXT",
    ".md": "MD",
    ".json": "JSON",
    ".xml": "XML",
  };
  return labels[extension] || extension.replace(".", "").toUpperCase();
}
