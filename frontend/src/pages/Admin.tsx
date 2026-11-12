import { FormEvent, useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, Doc, errMsg } from "../api";
import { useAuth } from "../auth";
import { Badge, Err, Title } from "../components/Layout";

const DEPTS = ["HR", "IT", "FINANCE", "POLICIES"]; const CLASSES = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"];

export default function Admin() {
  const { can } = useAuth();
  const [tab, setTab] = useState("overview"); const [error, setError] = useState(""); const [ok, setOk] = useState("");
  const [stats, setStats] = useState<any>(null); const [users, setUsers] = useState<any[]>([]); const [roles, setRoles] = useState<any[]>([]); const [docs, setDocs] = useState<Doc[]>([]);
  const fail = (e: any) => { setOk(""); setError(errMsg(e)); };
  const refresh = () => {
    api.get("/admin/stats").then((r) => setStats(r.data)).catch(fail);
    api.get("/users?page_size=100").then((r) => setUsers(r.data.items)).catch(fail);
    api.get("/admin/roles").then((r) => setRoles(r.data)).catch(fail);
    if (can("documents:manage_permissions")) api.get("/admin/documents?page_size=100").then((r) => setDocs(r.data.items)).catch(fail);
  };
  useEffect(refresh, []);

  const createUser = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault(); const f = new FormData(e.currentTarget);
    try { await api.post("/users", { email: f.get("email"), full_name: f.get("full_name"), password: f.get("password"), department_code: f.get("dept"), roles: [f.get("role")] }); setOk("User created"); setError(""); e.currentTarget.reset(); refresh(); } catch (x) { fail(x); }
  };
  const setUserRole = async (id: number, role: string) => { try { await api.put(`/admin/users/${id}/roles`, { roles: [role] }); setOk("Role updated"); setError(""); refresh(); } catch (x) { fail(x); } };
  const upload = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault(); const f = new FormData(e.currentTarget);
    f.set("allowed_roles", f.getAll("roles").join(",")); f.delete("roles");
    try { await api.post("/documents/upload", f); setOk("Document uploaded and indexed"); setError(""); e.currentTarget.reset(); refresh(); } catch (x) { fail(x); }
  };
  const setStatus = async (id: number, status: string) => { try { await api.put(`/documents/${id}/status`, { status }); setOk("Status updated"); setError(""); refresh(); } catch (x) { fail(x); } };
  const editRoles = async (d: Doc) => {
    const v = window.prompt("Allowed roles (comma separated)", (d.allowed_roles ?? []).join(","));
    if (v === null) return;
    try { await api.put(`/documents/${d.id}/permissions`, { allowed_roles: v.split(",").map((s) => s.trim()).filter(Boolean) }); setOk("Permissions updated"); setError(""); refresh(); } catch (x) { fail(x); }
  };
  const newVersion = async (id: number, file: File | undefined) => {
    if (!file) return; const f = new FormData(); f.set("file", file); f.set("activate", "true");
    try { await api.post(`/documents/${id}/versions`, f); setOk("New version indexed and activated"); setError(""); refresh(); } catch (x) { fail(x); }
  };

  const tabs = ["overview", "users", "documents", "roles"];
  return (
    <div>
      <Title sub="Users, roles and document permissions. Management views show metadata only, never content.">Administration</Title>
      <div className="mb-5 flex gap-2">{tabs.map((t) => <button key={t} onClick={() => setTab(t)} className={`rounded-md px-3 py-1.5 text-sm capitalize ${tab === t ? "bg-navy-800 text-white" : "border border-slate-300 bg-white"}`}>{t}</button>)}</div>
      <Err msg={error} />{ok && <div className="mb-4 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">{ok}</div>}

      {tab === "overview" && stats && (<div className="grid gap-5 lg:grid-cols-3">
        <div className="card"><div className="text-sm text-slate-500">Total users</div><div className="text-3xl font-semibold">{stats.total_users}</div></div>
        <div className="card"><div className="text-sm text-slate-500">Total documents</div><div className="text-3xl font-semibold">{stats.total_documents}</div></div>
        <div className="card"><div className="text-sm text-slate-500">By status</div><div className="mt-1 space-x-2">{Object.entries(stats.documents_by_status).map(([k, v]) => <span key={k}><Badge text={k} /> {String(v)}</span>)}</div></div>
        <div className="card lg:col-span-3"><h2 className="mb-3 font-medium">Documents by department</h2><div className="h-64"><ResponsiveContainer><BarChart data={Object.entries(stats.documents_by_department).map(([d, n]) => ({ department: d, documents: n }))}>
          <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="department" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="documents" fill="#12213f" /></BarChart></ResponsiveContainer></div></div></div>)}

      {tab === "users" && (<div className="grid gap-5 lg:grid-cols-3">
        <div className="card overflow-auto p-0 lg:col-span-2"><table className="w-full"><thead><tr>{["Name", "Email", "Dept", "Role"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>{users.map((u) => <tr key={u.id} className="border-t"><td className="td">{u.full_name}</td><td className="td">{u.email}</td><td className="td">{u.department}</td>
            <td className="td"><select className="input py-1" value={u.roles[0]} onChange={(e) => setUserRole(u.id, e.target.value)}>{roles.map((r) => <option key={r.name}>{r.name}</option>)}</select></td></tr>)}</tbody></table></div>
        <form onSubmit={createUser} className="card space-y-3"><h2 className="font-medium">Create user</h2>
          <input name="full_name" className="input" placeholder="Full name" required /><input name="email" type="email" className="input" placeholder="Email" required />
          <input name="password" type="password" className="input" placeholder="Password (12+ chars, mixed case, digit)" required />
          <select name="dept" className="input">{DEPTS.map((d) => <option key={d}>{d}</option>)}</select>
          <select name="role" className="input">{roles.map((r) => <option key={r.name}>{r.name}</option>)}</select><button className="btn">Create</button></form></div>)}

      {tab === "documents" && (<div className="space-y-5">
        <form onSubmit={upload} className="card grid gap-3 lg:grid-cols-3"><h2 className="font-medium lg:col-span-3">Upload document (PDF, DOCX, TXT)</h2>
          <input name="title" className="input" placeholder="Title" required /><select name="department_code" className="input">{DEPTS.map((d) => <option key={d}>{d}</option>)}</select>
          <select name="classification" className="input">{CLASSES.map((c) => <option key={c}>{c}</option>)}</select>
          <input name="file" type="file" accept=".pdf,.docx,.txt" className="input" required />
          <div className="text-sm lg:col-span-2"><div className="mb-1 text-slate-500">Allowed roles</div><div className="flex flex-wrap gap-3">{roles.filter((r) => r.name !== "SYSTEM_ADMIN").map((r) => <label key={r.name} className="flex items-center gap-1"><input type="checkbox" name="roles" value={r.name} />{r.name}</label>)}</div></div>
          <button className="btn w-fit">Upload</button></form>
        <div className="card overflow-auto p-0"><table className="w-full"><thead><tr>{["Title", "Dept", "Class.", "Status", "Ver.", "Allowed roles", "Actions"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>{docs.map((d) => <tr key={d.id} className="border-t"><td className="td">{d.title}</td><td className="td">{d.department}</td><td className="td"><Badge text={d.classification} /></td><td className="td"><Badge text={d.status} /></td><td className="td">v{d.current_version ?? "—"}</td>
            <td className="td max-w-xs text-xs">{d.allowed_roles?.join(", ")}</td>
            <td className="td space-x-2 whitespace-nowrap"><button className="text-gold-600 hover:underline" onClick={() => editRoles(d)}>Permissions</button>
              <select className="rounded border px-1 py-0.5 text-xs" value="" onChange={(e) => e.target.value && setStatus(d.id, e.target.value)}><option value="">Status…</option>{["ACTIVE", "ARCHIVED", "DELETED"].map((s) => <option key={s}>{s}</option>)}</select>
              <label className="cursor-pointer text-gold-600 hover:underline">New version<input type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={(e) => newVersion(d.id, e.target.files?.[0])} /></label></td></tr>)}</tbody></table></div></div>)}

      {tab === "roles" && (<div className="card overflow-auto p-0"><table className="w-full"><thead><tr><th className="th">Role</th><th className="th">Description</th><th className="th">Permissions</th></tr></thead>
        <tbody>{roles.map((r) => <tr key={r.name} className="border-t"><td className="td font-medium">{r.name}</td><td className="td">{r.description}</td><td className="td text-xs">{r.permissions.join(", ")}</td></tr>)}</tbody></table></div>)}
    </div>
  );
}
