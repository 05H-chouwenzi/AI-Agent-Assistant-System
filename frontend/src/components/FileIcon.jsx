export default function FileIcon({ type }) {
  const size = 20;
  switch (type) {
    case "pdf":
      return (
        <svg width={size} height={size} viewBox="0 0 30 36" fill="none">
          {/* PDF — red header */}
          <path d="M4 0a4 4 0 0 0-4 4v28a4 4 0 0 0 4 4h22a4 4 0 0 0 4-4V10l-8-10H4Z" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <path d="M22 0v6a4 4 0 0 0 4 4h4" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <rect x="3" y="15" width="24" height="17" rx="1.5" fill="#fff" stroke="#ef4444" strokeWidth="1.5" />
          <text x="15" y="27" fontSize="10" fill="#ef4444" fontWeight="bold" textAnchor="middle" fontFamily="Segoe UI,sans-serif">PDF</text>
        </svg>
      );
    case "docx":
    case "doc":
      return (
        <svg width={size} height={size} viewBox="0 0 30 36" fill="none">
          {/* Word — blue header */}
          <path d="M4 0a4 4 0 0 0-4 4v28a4 4 0 0 0 4 4h22a4 4 0 0 0 4-4V10l-8-10H4Z" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <path d="M22 0v6a4 4 0 0 0 4 4h4" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <rect x="3" y="15" width="24" height="17" rx="1.5" fill="#2563eb" />
          {/* W icon in white */}
          <path d="M8 25l2.5-7h1l2 5 2-5h1l2.5 7h-1.2l-2-5.5-1.8 5h-1l-1.8-5-2 5.5H8Z" fill="#fff" />
        </svg>
      );
    case "xlsx":
    case "xls":
      return (
        <svg width={size} height={size} viewBox="0 0 30 36" fill="none">
          {/* Excel — green header */}
          <path d="M4 0a4 4 0 0 0-4 4v28a4 4 0 0 0 4 4h22a4 4 0 0 0 4-4V10l-8-10H4Z" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <path d="M22 0v6a4 4 0 0 0 4 4h4" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <rect x="3" y="15" width="24" height="17" rx="1.5" fill="#16a34a" />
          {/* X icon in white */}
          <text x="15" y="28" fontSize="12" fill="#fff" fontWeight="bold" textAnchor="middle" fontFamily="Segoe UI,sans-serif">X</text>
        </svg>
      );
    case "pptx":
    case "ppt":
      return (
        <svg width={size} height={size} viewBox="0 0 30 36" fill="none">
          {/* PowerPoint — red-orange header */}
          <path d="M4 0a4 4 0 0 0-4 4v28a4 4 0 0 0 4 4h22a4 4 0 0 0 4-4V10l-8-10H4Z" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <path d="M22 0v6a4 4 0 0 0 4 4h4" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <rect x="3" y="15" width="24" height="17" rx="1.5" fill="#d97706" />
          {/* P icon in white */}
          <text x="15" y="28" fontSize="12" fill="#fff" fontWeight="bold" textAnchor="middle" fontFamily="Segoe UI,sans-serif">P</text>
        </svg>
      );
    case "md":
    case "markdown":
      return (
        <svg width={size} height={size} viewBox="0 0 30 36" fill="none">
          <path d="M4 0a4 4 0 0 0-4 4v28a4 4 0 0 0 4 4h22a4 4 0 0 0 4-4V10l-8-10H4Z" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <path d="M22 0v6a4 4 0 0 0 4 4h4" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <rect x="3" y="15" width="24" height="17" rx="1.5" fill="#6366f1" />
          <text x="15" y="28" fontSize="10" fill="#fff" fontWeight="bold" textAnchor="middle" fontFamily="Segoe UI,sans-serif">MD</text>
        </svg>
      );
    case "png":
    case "jpg":
    case "jpeg":
    case "bmp":
    case "tiff":
    case "tif":
    case "webp":
      return (
        <svg width={size} height={size} viewBox="0 0 30 36" fill="none">
          {/* Image — teal header */}
          <path d="M4 0a4 4 0 0 0-4 4v28a4 4 0 0 0 4 4h22a4 4 0 0 0 4-4V10l-8-10H4Z" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <path d="M22 0v6a4 4 0 0 0 4 4h4" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <rect x="3" y="15" width="24" height="17" rx="1.5" fill="#0d9488" />
          {/* mountain/sun icon */}
          <path d="M7 26l4-6 3 4 2.5-3 3.5 5H7Z" fill="#fff" opacity="0.6" />
          <circle cx="20" cy="19" r="2" fill="#fff" opacity="0.8" />
        </svg>
      );
    default:
      return (
        <svg width={size} height={size} viewBox="0 0 30 36" fill="none">
          {/* TXT — gray header */}
          <path d="M4 0a4 4 0 0 0-4 4v28a4 4 0 0 0 4 4h22a4 4 0 0 0 4-4V10l-8-10H4Z" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <path d="M22 0v6a4 4 0 0 0 4 4h4" fill="#fff" stroke="#d1d5db" strokeWidth="0.8" />
          <rect x="3" y="15" width="24" height="17" rx="1.5" fill="#6b7280" />
          <text x="15" y="28" fontSize="10" fill="#fff" fontWeight="bold" textAnchor="middle" fontFamily="Segoe UI,sans-serif">TXT</text>
        </svg>
      );
  }
}
