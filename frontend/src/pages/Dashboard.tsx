import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Doc, errMsg } from "../api";
import { useAuth } from "../auth";
import { Badge, Err, Title } from "../components/Layout";

export default function Dashboard() {
  const { user, can } = useAuth();
  const [access, setAccess] = useState<any>(null);
  const [sessions, setSessions] = useState<any[]>([]);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    api.get("/users/me/access").then((r) => setAccess(r.data)).catch((e) => setError(errMsg(e)));
    if (can("chat:use")) api.get("/chat/sessions").then((r) => setSessions(r.data.slice(0, 5))).catch(() => {});
    if (can("documents:read")) api.get("/documents?page_size=5").then((r) => setDocs(r.data.items)).catch(() => {});
  }, []);
  return (
    <div>
      <Title sub={`${user?.department} · ${user?.roles.join(", ")}`}>{`Welcome, ${user?.full_name}`}</Title>
      <Err msg={error} />
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="card"><h2 className="mb-3 font-medium">Accessible document categories</h2>
          {access?.accessible_document_categories?.length ? (
            <table className="w-full"><thead><tr><th className="th">Department</th><th className="th">Classification</th><th className="th">Documents</th></tr></thead>
              <tbody>{access.accessible_document_categories.map((c: any) => (
                <tr key={c.department + c.classification} className="border-t"><td className="td">{c.department}</td><td className="td"><Badge text={c.classification} /></td><td className="td">{c.documents}</td></tr>))}</tbody></table>
          ) : <p className="text-sm text-slate-500">No documents are shared with your roles.</p>}
        </div>
        <div className="card"><h2 className="mb-3 font-medium">Restrictions</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">{access?.restrictions?.map((r: string) => <li key={r}>{r}</li>)}</ul></div>
        <div className="card"><h2 className="mb-3 font-medium">Recent conversations</h2>
          {sessions.length ? sessions.map((s) => <Link key={s.id} to="/chat" className="block border-t py-2 text-sm text-slate-700 hover:text-gold-600">{s.title}</Link>) : <p className="text-sm text-slate-500">No conversations yet.</p>}</div>
        <div className="card"><h2 className="mb-3 font-medium">Recent authorized documents</h2>
          {docs.length ? docs.map((d) => <div key={d.id} className="flex justify-between border-t py-2 text-sm"><span>{d.title}</span><Badge text={d.classification} /></div>) : <p className="text-sm text-slate-500">No documents.</p>}</div>
      </div>
    </div>
  );
}
