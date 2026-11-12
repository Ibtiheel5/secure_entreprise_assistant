import { FormEvent, useEffect, useRef, useState } from "react";
import { api, Citation, errMsg } from "../api";
import { Err, Title } from "../components/Layout";

type Msg = { role: string; content: string; citations?: Citation[] | null; grounded?: boolean };

export default function Chat() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [sid, setSid] = useState<number | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const loadSessions = () => api.get("/chat/sessions").then((r) => setSessions(r.data)).catch((e) => setError(errMsg(e)));
  useEffect(() => { loadSessions(); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  const open = async (id: number) => {
    setError("");
    try { const { data } = await api.get(`/chat/sessions/${id}`); setSid(id); setMsgs(data.messages); } catch (e) { setError(errMsg(e)); }
  };
  const send = async (e: FormEvent) => {
    e.preventDefault();
    const q = text.trim(); if (!q || busy) return;
    setText(""); setError(""); setBusy(true); setMsgs((m) => [...m, { role: "user", content: q }]);
    try {
      const { data } = await api.post("/chat", { message: q, session_id: sid });
      setSid(data.session_id);
      setMsgs((m) => [...m, { role: "assistant", content: data.answer, citations: data.citations, grounded: data.grounded }]);
      loadSessions();
    } catch (x) { setError(errMsg(x)); } finally { setBusy(false); }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <Title sub="Answers use only documents you are authorized to access. Sources are cited.">AI Assistant</Title>
      <div className="flex min-h-0 flex-1 gap-5">
        <div className="card w-60 shrink-0 overflow-auto p-3">
          <button className="btn-ghost mb-2 w-full justify-center" onClick={() => { setSid(null); setMsgs([]); }}>New conversation</button>
          {sessions.map((s) => <button key={s.id} onClick={() => open(s.id)} className={`block w-full truncate rounded px-2 py-1.5 text-left text-sm ${s.id === sid ? "bg-slate-100" : "hover:bg-slate-50"}`}>{s.title}</button>)}
        </div>
        <div className="card flex min-w-0 flex-1 flex-col p-0">
          <div className="flex-1 space-y-4 overflow-auto p-5">
            {!msgs.length && <p className="text-sm text-slate-500">Ask a question about company policies and procedures.</p>}
            {msgs.map((m, i) => (
              <div key={i} className={m.role === "user" ? "text-right" : ""}>
                <div className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-lg px-4 py-2 text-left text-sm ${m.role === "user" ? "bg-navy-800 text-white" : m.grounded === false ? "border border-amber-200 bg-amber-50 text-amber-900" : "bg-slate-100 text-slate-800"}`}>{m.content}</div>
                {!!m.citations?.length && (
                  <div className="mt-2 flex flex-wrap gap-2">{m.citations.map((c) => (
                    <span key={c.source_id} className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600">[{c.source_id}] {c.title} · v{c.version} · {c.department}</span>))}</div>)}
              </div>))}
            {busy && <div className="text-sm text-slate-500">Searching authorized documents and generating an answer…</div>}
            <div ref={end} />
          </div>
          <div className="border-t p-4"><Err msg={error} />
            <form onSubmit={send} className="flex gap-3"><input className="input" value={text} maxLength={4000} onChange={(e) => setText(e.target.value)} placeholder="Ask a question…" />
              <button className="btn" disabled={busy || !text.trim()}>Send</button></form></div>
        </div>
      </div>
    </div>
  );
}
