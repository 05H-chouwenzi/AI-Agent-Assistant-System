/**
 * 知识库 API
 */
import api from "./client";

export async function uploadDoc(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post("/api/knowledge/upload", form);
  return res.data;
}

export async function listDocs(params = {}) {
  const res = await api.get("/api/knowledge/docs", { params });
  return res.data;
}

export async function deleteDoc(id) {
  const res = await api.delete(`/api/knowledge/docs/${id}`);
  return res.data;
}
