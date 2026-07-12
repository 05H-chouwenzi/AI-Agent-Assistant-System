/**
 * useChat — 聊天状态管理 Hook
 *
 * 当前实现为 ChatContext 的透明代理，保持与旧组件的兼容。
 * 所有状态（包括 SSE 流式连接）在 ChatContext 中全局管理，
 * 页面切换时不会中断正在进行的 AI 回复。
 */
export { useChat, STATUS_STEPS } from "../contexts/ChatContext";
