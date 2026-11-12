import axios from "axios";

const TOKEN_KEY = "sea_token"; // sessionStorage : effacé à la fermeture de l'onglet (compromis XSS documenté dans le README)
export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) => (t ? sessionStorage.setItem(TOKEN_KEY, t) : sessionStorage.removeItem(TOKEN_KEY));

export const api = axios.create({ baseURL: "/api" });
api.interceptors.request.use((c) => { const t = getToken(); if (t) c.headers.Authorization = `Bearer ${t}`; return c; });
api.interceptors.response.use((r) => r, (e) => {
  if (e.response?.status === 401 && !e.config.url?.includes("/auth/login")) { setToken(null); window.location.assign("/login"); }
  return Promise.reject(e);
});

export const errMsg = (e: any): string => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg).join("; ");
  return e?.message ?? "Unexpected error";
};

export type Me = { id: number; email: string; full_name: string; department: string; roles: string[]; permissions: string[] };
export type Doc = { id: number; title: string; department: string; classification: string; status: string; current_version: number | null; updated_at: string; allowed_roles?: string[] | null };
export type Citation = { source_id: string; document_id: number; title: string; department: string; version: number; chunk_id: number };
