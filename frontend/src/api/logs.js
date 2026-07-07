/**
 * 日志 API
 */
import api from "./client";

export async function getLogs(params = {}) {
  const res = await api.get("/api/logs/", { params });
  return res.data;
}

export async function getLogActions() {
  const res = await api.get("/api/logs/actions");
  return res.data;
}

export async function getLogModules() {
  const res = await api.get("/api/logs/modules");
  return res.data;
}
