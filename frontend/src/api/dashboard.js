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

/** 获取仪表盘统计数据 */
export async function getDashboardStats() {
  const res = await api.get("/api/dashboard/stats");
  return res.data;
}

/** 获取仪表盘趋势数据（近7天） */
export async function getDashboardTrends() {
  const res = await api.get("/api/dashboard/trends");
  return res.data;
}

/** 获取系统状态信息 */
export async function getDashboardSystem() {
  const res = await api.get("/api/dashboard/system");
  return res.data;
}
