/**
 * 仪表盘 API
 */
import api from "./client";

/** 获取仪表盘统计数据（60s timeout — 首次加载可能较慢） */
export async function getDashboardStats() {
  const res = await api.get("/api/dashboard/stats", { timeout: 60000 });
  return res.data;
}

/** 获取仪表盘趋势数据（近7天） */
export async function getDashboardTrends() {
  const res = await api.get("/api/dashboard/trends", { timeout: 60000 });
  return res.data;
}

/** 获取系统状态信息 */
export async function getDashboardSystem() {
  const res = await api.get("/api/dashboard/system", { timeout: 60000 });
  return res.data;
}
