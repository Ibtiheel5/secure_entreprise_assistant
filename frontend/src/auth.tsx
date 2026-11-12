import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, getToken, Me, setToken } from "./api";

type Ctx = { user: Me | null; loading: boolean; login: (e: string, p: string) => Promise<void>; logout: () => Promise<void>; can: (p: string) => boolean };
const AuthCtx = createContext<Ctx>(null as unknown as Ctx);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(!!getToken());

  useEffect(() => {
    if (!getToken()) return;
    api.get<Me>("/auth/me").then((r) => setUser(r.data)).catch(() => setToken(null)).finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const { data } = await api.post("/auth/login", { email, password });
    setToken(data.access_token);
    setUser((await api.get<Me>("/auth/me")).data); // l'identité vient toujours du serveur
  };
  const logout = async () => { try { await api.post("/auth/logout"); } finally { setToken(null); setUser(null); } };
  const can = (p: string) => !!user?.permissions.includes(p);
  return <AuthCtx.Provider value={{ user, loading, login, logout, can }}>{children}</AuthCtx.Provider>;
}
