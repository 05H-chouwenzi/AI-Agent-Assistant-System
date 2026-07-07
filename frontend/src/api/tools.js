/**
 * 工具中心 API
 */
import api from "./client";

/** 查询天气 */
export async function queryWeather(city, days = 1) {
  const res = await api.post("/api/tools/weather", { city, days });
  return res.data;
}

/** 执行数据库查询（只读） */
export async function executeDatabaseQuery(query, limit = 50) {
  const res = await api.post("/api/tools/mysql", { query, limit });
  return res.data;
}

/** 发送 HTTP 请求 */
export async function sendHttpRequest(url, method = "GET", headers = {}, body = "") {
  const res = await api.post("/api/tools/http", { url, method, headers, body });
  return res.data;
}

/** 搜索企业内部知识库 */
export async function searchKnowledge(query, top_k = 5) {
  const res = await api.post("/api/tools/rag", { query, top_k });
  return res.data;
}
