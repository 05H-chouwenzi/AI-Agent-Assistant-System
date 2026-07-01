import axios from "axios";

const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_BASE_URL || "http://localhost:8004"}/api`,
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

export async function uploadDoc(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post("/knowledge/upload", form);
  return res.data;
}

export async function listDocs(params = {}) {
  const res = await api.get("/knowledge/docs", { params });
  return res.data;
}

export async function deleteDoc(id) {
  const res = await api.delete(`/knowledge/docs/${id}`);
  return res.data;
}
