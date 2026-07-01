import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8004",
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 401 自动跳转登录
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("username");
      localStorage.removeItem("user_id");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

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
