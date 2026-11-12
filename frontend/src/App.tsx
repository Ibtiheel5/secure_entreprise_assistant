import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Chat from "./pages/Chat";
import Documents from "./pages/Documents";
import Admin from "./pages/Admin";
import Security from "./pages/Security";
import MLOps from "./pages/MLOps";
import { ReactNode } from "react";

function Guard({ perm, children }: { perm?: string; children: ReactNode }) {
  const { user, loading, can } = useAuth();
  if (loading) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (perm && !can(perm)) return <div className="p-8 text-sm text-slate-600">Access denied for your role.</div>;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Guard><Layout /></Guard>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/chat" element={<Guard perm="chat:use"><Chat /></Guard>} />
        <Route path="/documents" element={<Guard perm="documents:read"><Documents /></Guard>} />
        <Route path="/admin" element={<Guard perm="users:manage"><Admin /></Guard>} />
        <Route path="/security" element={<Guard perm="security:view"><Security /></Guard>} />
        <Route path="/mlops" element={<Guard perm="ml:view"><MLOps /></Guard>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
