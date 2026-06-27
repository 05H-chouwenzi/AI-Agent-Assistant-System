import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000",
  timeout: 30000,
});

// 每次请求自动带上 token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** 登录 */
export async function login(username, password) {
  const res = await api.post("/api/users/login", { username, password });
  return res.data;
}

/** 注册 */
export async function register(username, password) {
  const res = await api.post("/api/users/register", { username, password });
  return res.data;
}

/** 发送消息给 Agent */
export async function sendMessage(question) {
  const res = await api.post("/api/chat/send", { question });
  return res.data;
}

/** 获取会话列表 */
export async function getConversations() {
  const res = await api.get("/api/conversations/");
  return res.data;
}

/** 创建会话 */
export async function createConversation(title = "新对话") {
  const res = await api.post("/api/conversations/", { title });
  return res.data;
}

/** 删除会话 */
export async function deleteConversation(id) {
  await api.delete(`/api/conversations/${id}`);
}

/** 获取会话消息列表 */
export async function getConversationMessages(convId) {
  const res = await api.get(`/api/conversations/${convId}/messages`);
  return res.data;
}
