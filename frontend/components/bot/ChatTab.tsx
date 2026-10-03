"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Arrow } from "@/components/icons";
import { api, Bot, Provider, Source, streamChat } from "@/lib/api";

type Msg = { role: "user" | "assistant" | "error"; content: string; sources?: Source[]; meta?: { provider: string; model: string; first_token_ms: number | null; total_ms: number; retrieval_ms: number } };

export default function ChatTab({ bot }: { bot: Bot }) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [provider, setProvider] = useState(bot.llm_provider ?? "");
  const [model, setModel] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => { api<Provider[]>("/providers").then(setProviders).catch(() => {}); }, []);
  useEffect(() => { box.current?.scrollTo({ top: box.current.scrollHeight }); }, [msgs]);
  useEffect(() => () => abort.current?.abort(), []);

  const current = providers.find((p) => p.name === (provider || providers.find((x) => x.is_default)?.name));

  async function send(e: FormEvent) {
    e.preventDefault();
    const message = q.trim();
    if (!message || busy) return;
    const history = msgs.filter((m) => m.role !== "error").map(({ role, content }) => ({ role, content }));
    setQ(""); setBusy(true);
    setMsgs((m) => [...m, { role: "user", content: message }, { role: "assistant", content: "" }]);
    const patch = (fn: (last: Msg) => Msg) => setMsgs((m) => [...m.slice(0, -1), fn(m[m.length - 1])]);
    abort.current = new AbortController();
    try {
      await streamChat(`/bots/${bot.id}/chat`, { message, history, provider: provider || null, model: model || null }, (ev) => {
        if (ev.type === "token") patch((l) => ({ ...l, content: l.content + ev.text }));
        else if (ev.type === "sources") patch((l) => ({ ...l, sources: ev.items }));
        else if (ev.type === "done") patch((l) => ({ ...l, meta: ev }));
        else if (ev.type === "error") patch(() => ({ role: "error", content: ev.message }));
      }, abort.current.signal);
    } catch (err) {
      patch(() => ({ role: "error", content: (err as Error).message }));
    } finally { setBusy(false); }
  }

  return (
    <div className="card chat">
      <div className="chat-bar">
        <label className="hint" htmlFor="prov">provider</label>
        <select id="prov" className="select" style={{ width: 190, height: 40 }} value={provider} onChange={(e) => { setProvider(e.target.value); setModel(""); }}>
          <option value="">bot default{bot.llm_provider ? ` (${bot.llm_provider})` : ""}</option>
          {providers.map((p) => (
            <option key={p.name} value={p.name} disabled={!p.configured}>{p.name}{p.configured ? "" : " · no key"}</option>
          ))}
        </select>
        <input className="input" style={{ width: 230, height: 40 }} placeholder={current ? current.default_model : "model"} aria-label="model override" value={model} onChange={(e) => setModel(e.target.value)} />
        <span style={{ flex: 1 }} />
        <button className="btn ghost sm" onClick={() => setMsgs([])} disabled={busy || !msgs.length}>clear</button>
      </div>

      <div className="chat-msgs" ref={box} aria-live="polite">
        {msgs.length === 0 && (
          <div className="bubble bot">{bot.greeting}<div className="hint" style={{ marginTop: 6 }}>this is a private test chat. switch providers above to compare answers and latency.</div></div>
        )}
        {msgs.map((m, i) =>
          m.role === "user" ? <div key={i} className="bubble user">{m.content}</div>
          : m.role === "error" ? <div key={i} className="bubble err" role="alert">⚠ {m.content}</div>
          : (
            <div key={i} className="bubble bot">
              {m.content || <span className="typing"><span /><span /><span /></span>}
              {m.meta && (
                <div className="meta">
                  <span className="chip ok">{m.meta.provider}</span>
                  <span className="chip plain">{m.meta.model}</span>
                  <span className="chip plain">first token {m.meta.first_token_ms ?? "–"} ms</span>
                  <span className="chip plain">total {m.meta.total_ms} ms</span>
                </div>
              )}
              {!!m.sources?.length && (
                <details className="sources">
                  <summary>{m.sources.length} source{m.sources.length > 1 ? "s" : ""}</summary>
                  <ol>{m.sources.map((s) => <li key={s.n}><b>{s.filename}</b>: {s.snippet.replace(/\s+/g, " ")}…</li>)}</ol>
                </details>
              )}
            </div>
          ))}
      </div>

      <form className="chat-form" onSubmit={send}>
        <input className="input" placeholder={bot.n_documents ? "ask something about your documents…" : "upload a document first, or just say hi…"} aria-label="message" maxLength={2000} value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="send" aria-label="send" disabled={busy || !q.trim()}><Arrow /></button>
      </form>
    </div>
  );
}
