import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";

export default function Layout() {
  const { user, logout, can } = useAuth();
  const items = [
    { to: "/", label: "Dashboard", show: true },
    { to: "/chat", label: "AI Assistant", show: can("chat:use") },
    { to: "/documents", label: "Documents", show: can("documents:read") },
    { to: "/admin", label: "Administration", show: can("users:manage") },
    { to: "/security", label: "Security", show: can("security:view") },
    { to: "/mlops", label: "MLOps", show: can("ml:view") },
  ];
  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 shrink-0 flex-col bg-navy-900 text-slate-200">
        <div className="border-b border-navy-700 px-5 py-5">
          <div className="text-xs uppercase tracking-widest text-gold-500">Enterprise</div>
          <div className="text-base font-semibold text-white">Knowledge Assistant</div>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {items.filter((i) => i.show).map((i) => (
            <NavLink key={i.to} to={i.to} end={i.to === "/"}
              className={({ isActive }) => `block rounded-md px-3 py-2 text-sm ${isActive ? "bg-navy-700 text-white" : "hover:bg-navy-800"}`}>
              {i.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-navy-700 p-4 text-xs">
          <div className="font-medium text-white">{user?.full_name}</div>
          <div className="text-slate-400">{user?.roles.join(", ")}</div>
          <button onClick={logout} className="mt-3 text-gold-500 hover:underline">Sign out</button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto bg-slate-50 p-8"><Outlet /></main>
    </div>
  );
}

export const Title = ({ children, sub }: { children: string; sub?: string }) => (
  <div className="mb-6"><h1 className="text-xl font-semibold text-navy-900">{children}</h1>{sub && <p className="text-sm text-slate-500">{sub}</p>}</div>
);
export const Err = ({ msg }: { msg: string }) => msg ? <div role="alert" className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{msg}</div> : null;
export const Badge = ({ text }: { text: string }) => {
  const c: Record<string, string> = { PUBLIC: "bg-green-50 text-green-700", INTERNAL: "bg-blue-50 text-blue-700", CONFIDENTIAL: "bg-amber-50 text-amber-700", RESTRICTED: "bg-red-50 text-red-700",
    ACTIVE: "bg-green-50 text-green-700", DRAFT: "bg-slate-100 text-slate-600", ARCHIVED: "bg-slate-100 text-slate-600", DELETED: "bg-red-50 text-red-700" };
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${c[text] ?? "bg-slate-100 text-slate-600"}`}>{text}</span>;
};
