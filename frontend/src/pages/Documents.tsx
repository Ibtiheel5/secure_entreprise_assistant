import { useEffect, useState } from "react";
import { api, Doc, errMsg } from "../api";
import { Badge, Err, Title } from "../components/Layout";

export default function Documents() {
  const [items, setItems] = useState<Doc[]>([]); const [total, setTotal] = useState(0); const [page, setPage] = useState(1);
  const [query, setQuery] = useState(""); const [dept, setDept] = useState("");
  const [versions, setVersions] = useState<{ doc: Doc; rows: any[] } | null>(null); const [error, setError] = useState("");
  const load = () => api.get("/documents", { params: { query: query || undefined, department: dept || undefined, page, page_size: 15 } })
    .then((r) => { setItems(r.data.items); setTotal(r.data.total); setError(""); }).catch((e) => setError(errMsg(e)));
  useEffect(() => { load(); }, [page, dept]);
  const showVersions = async (doc: Doc) => { try { setVersions({ doc, rows: (await api.get(`/documents/${doc.id}/versions`)).data }); } catch (e) { setError(errMsg(e)); } };
  return (
    <div>
      <Title sub="Only documents shared with your roles are listed.">Document Explorer</Title>
      <Err msg={error} />
      <div className="mb-4 flex gap-3">
        <input className="input max-w-xs" placeholder="Search by title" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (setPage(1), load())} />
        <select className="input max-w-[12rem]" value={dept} onChange={(e) => { setPage(1); setDept(e.target.value); }}>
          <option value="">All departments</option>{["HR", "IT", "FINANCE", "POLICIES"].map((d) => <option key={d}>{d}</option>)}</select>
        <button className="btn" onClick={() => { setPage(1); load(); }}>Search</button>
      </div>
      <div className="card overflow-auto p-0"><table className="w-full"><thead><tr>{["Title", "Department", "Classification", "Status", "Version", "Updated", ""].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody>{items.map((d) => (<tr key={d.id} className="border-t"><td className="td font-medium">{d.title}</td><td className="td">{d.department}</td><td className="td"><Badge text={d.classification} /></td>
          <td className="td"><Badge text={d.status} /></td><td className="td">v{d.current_version ?? "—"}</td><td className="td">{new Date(d.updated_at).toLocaleDateString()}</td>
          <td className="td"><button className="text-gold-600 hover:underline" onClick={() => showVersions(d)}>History</button></td></tr>))}
          {!items.length && <tr><td className="td text-slate-500" colSpan={7}>No documents found.</td></tr>}</tbody></table></div>
      <div className="mt-3 flex items-center gap-3 text-sm text-slate-600"><button className="btn-ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
        <span>Page {page} · {total} documents</span><button className="btn-ghost" disabled={page * 15 >= total} onClick={() => setPage(page + 1)}>Next</button></div>
      {versions && (<div className="fixed inset-0 flex items-center justify-center bg-black/30" onClick={() => setVersions(null)}><div className="card w-96" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-3 font-medium">{versions.doc.title}</h2><p className="mb-2 text-xs text-slate-500">Version metadata only; archived content is never served.</p>
        {versions.rows.map((v) => <div key={v.version_number} className="flex justify-between border-t py-2 text-sm"><span>Version {v.version_number}</span><Badge text={v.status} /></div>)}
        <button className="btn-ghost mt-4" onClick={() => setVersions(null)}>Close</button></div></div>)}
    </div>
  );
}
