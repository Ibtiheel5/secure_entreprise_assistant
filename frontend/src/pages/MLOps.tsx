import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, errMsg } from "../api";
import { useAuth } from "../auth";
import { Badge, Err, Title } from "../components/Layout";

const KEYS = ["mrr@10", "ndcg@10", "recall@10", "precision@5"];
const COLORS = ["#12213f", "#b8923a", "#4b6cb7", "#7a8ba8"];

export default function MLOps() {
  const { can } = useAuth();
  const [models, setModels] = useState<any>(null); const [ev, setEv] = useState<any>(null); const [error, setError] = useState("");
  const load = () => { api.get("/ml/models").then((r) => setModels(r.data)).catch((e) => setError(errMsg(e))); api.get("/ml/evaluation").then((r) => setEv(r.data)).catch((e) => setError(errMsg(e))); };
  useEffect(load, []);
  const deploy = async (id: number) => { try { await api.post(`/ml/models/${id}/deploy`); load(); } catch (e) { setError(errMsg(e)); } };
  const chart = KEYS.map((k) => ({ metric: k, ...Object.fromEntries((ev?.models ?? []).map((m: any) => [m.version, m.metrics?.[k] ?? 0])) }));
  return (
    <div>
      <Title sub="Data comes from the model_experiments table, filled by the training/evaluation scripts.">MLOps Dashboard</Title>
      <Err msg={error} />
      {models && <div className="card mb-5"><div className="text-sm text-slate-500">Reranker currently serving</div><div className="font-mono text-sm">{models.serving_model}</div></div>}
      {ev && !ev.models.length && <div className="card text-sm text-slate-600">No experiments recorded yet. Train and evaluate a reranker (see docs/evaluation) and run <code>evaluate_reranker.py --register-db</code>.</div>}
      {!!ev?.models.length && (<>
        <div className="card mb-5"><h2 className="mb-3 font-medium">Baseline vs fine-tuned</h2>
          {!ev.baseline_available && <p className="mb-2 text-sm text-amber-700">No model is tagged “baseline”; deltas cannot be computed.</p>}
          <div className="h-72"><ResponsiveContainer><BarChart data={chart}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="metric" /><YAxis domain={[0, 1]} /><Tooltip /><Legend />
            {ev.models.map((m: any, i: number) => <Bar key={m.version} dataKey={m.version} fill={COLORS[i % COLORS.length]} />)}</BarChart></ResponsiveContainer></div></div>
        <div className="card overflow-auto p-0"><table className="w-full"><thead><tr>{["Version", "Model", "Metrics", "Δ vs baseline", "Created", ""].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>{ev.models.map((m: any) => <tr key={m.id} className="border-t"><td className="td font-medium">{m.version} {m.is_deployed && <Badge text="DEPLOYED" />}</td><td className="td font-mono text-xs">{m.model_name}</td>
            <td className="td text-xs">{KEYS.map((k) => `${k}: ${m.metrics?.[k]?.toFixed(3)}`).join(" · ")}</td>
            <td className="td text-xs">{m.delta_vs_baseline ? KEYS.map((k) => `${k}: ${m.delta_vs_baseline[k] >= 0 ? "+" : ""}${m.delta_vs_baseline[k]?.toFixed(3)}`).join(" · ") : "—"}</td>
            <td className="td">{new Date(m.created_at).toLocaleDateString()}</td>
            <td className="td">{can("ml:manage") && !m.is_deployed && m.params?.model_path && <button className="btn-ghost" onClick={() => deploy(m.id)}>Deploy</button>}</td></tr>)}</tbody></table></div></>)}
    </div>
  );
}
