import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, errMsg } from "../api";
import { Err, Title } from "../components/Layout";

export default function Security() {
  const [ov, setOv] = useState<any>(null); const [logs, setLogs] = useState<any>(null); const [page, setPage] = useState(1);
  const [denied, setDenied] = useState(false); const [error, setError] = useState("");
  useEffect(() => { api.get("/security/overview").then((r) => setOv(r.data)).catch((e) => setError(errMsg(e))); }, []);
  useEffect(() => { api.get("/security/audit-logs", { params: { page, denied_only: denied, page_size: 15 } }).then((r) => setLogs(r.data)).catch((e) => setError(errMsg(e))); }, [page, denied]);
  const Card = ({ label, value }: { label: string; value: any }) => <div className="card"><div className="text-sm text-slate-500">{label}</div><div className="text-2xl font-semibold">{value}</div></div>;
  return (
    <div>
      <Title sub="Computed from the audit log (access_logs). Nothing on this page is hardcoded.">Security Dashboard</Title>
      <Err msg={error} />
      {ov && (<>
        <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
          <Card label="Total attempts" value={ov.total_access_attempts} /><Card label="Authorized" value={ov.authorized_requests} /><Card label="Denied" value={ov.denied_requests} />
          <Card label="Auth failures" value={ov.auth_failures} /><Card label="Unauthorized doc attempts" value={ov.unauthorized_document_attempts} /><Card label="Injection suspected" value={ov.prompt_injection_suspected} />
        </div>
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <div className="card"><h2 className="mb-3 font-medium">Department-level access</h2><div className="h-64"><ResponsiveContainer><BarChart data={ov.by_department}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="department" /><YAxis allowDecimals={false} /><Tooltip /><Legend /><Bar dataKey="requests" fill="#12213f" /><Bar dataKey="denied" fill="#b8923a" /></BarChart></ResponsiveContainer></div></div>
          <div className="card"><h2 className="mb-3 font-medium">Security test results</h2>
            {ov.security_tests ? (<div className="text-sm"><p>{ov.security_tests.passed}/{ov.security_tests.total} passed ({(ov.security_tests.pass_rate * 100).toFixed(1)}%)</p>
              <p>Prompt-injection tests: {ov.security_tests.prompt_injection.passed}/{ov.security_tests.prompt_injection.total}</p>
              <p className="mt-2 text-xs text-slate-500">Last run: {new Date(ov.security_tests.ran_at).toLocaleString()}</p></div>)
              : <p className="text-sm text-slate-500">No report yet. Run <code>python scripts/run_security_suite.py</code>.</p>}</div>
        </div></>)}
      <div className="card mt-5 overflow-auto p-0"><div className="flex items-center justify-between p-4"><h2 className="font-medium">Audit log</h2>
        <label className="text-sm"><input type="checkbox" className="mr-2" checked={denied} onChange={(e) => { setPage(1); setDenied(e.target.checked); }} />Denied only</label></div>
        <table className="w-full"><thead><tr>{["Time", "User", "Action", "Resource", "Allowed", "Reason"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>{logs?.items.map((l: any) => <tr key={l.id} className="border-t"><td className="td">{new Date(l.created_at).toLocaleString()}</td><td className="td">{l.user_id ?? "—"}</td><td className="td">{l.action}</td><td className="td">{l.resource_type ? `${l.resource_type}/${l.resource_id}` : "—"}</td>
            <td className="td">{l.allowed ? "yes" : <span className="font-medium text-red-600">no</span>}</td><td className="td text-xs">{l.reason}</td></tr>)}</tbody></table>
        <div className="flex items-center gap-3 p-3 text-sm"><button className="btn-ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button><span>Page {page}</span><button className="btn-ghost" disabled={!logs || page * 15 >= logs.total} onClick={() => setPage(page + 1)}>Next</button></div></div>
    </div>
  );
}
