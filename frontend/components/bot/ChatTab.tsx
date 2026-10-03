"use client";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Arrow } from "@/components/icons";
import Sources from "@/components/bot/Sources";
import { api, Bot, Conversation, fmtTime, Source, StoredMessage, streamChat } from "@/lib/api";

type Meta = { provider: string | null; model: string | null; grounded?: boolean; first_token_ms: number | null; total_ms: number | null };
type Msg = { role: "user" | "assistant" | "error"; content: string; sources?: Source[]; meta?: Meta };

const fromStored = (m: StoredMessage): Msg => ({
  role: m.role, content: m.content, sources: m.sources,
  meta: m.role === "assistant"
    ? { provider: m.provider, model: m.model, grounded: !!m.provider, first_token_ms: m.first_token_ms, total_ms: m.total_ms }
    : undefined,
});

/** Private test chat. Answers come from the bot's documents through its configured provider;
 *  every chat is saved, and earlier dashboard chats can be picked up again. */
export default function ChatTab({ bot, initialConversationId }: { bot: Bot; initialConversationId?: string | null }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null); // server keeps the history
  const [recent, setRecent] = useState<Conversation[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const box = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);

  const loadRecent = useCallback(() =>
    api<Conversation[]>(`/bots/${bot.id}/conversations?source=dashboard&limit=30`).then(setRecent).catch(() => {}), [bot.id]);

  const open = useCallback(async (cid: string | null) => {
    abort.current?.abort();
    setError("");
    if (!cid) { setConversationId(null); setMsgs([]); return; }
    try {
      const d = await api<{ messages: StoredMessage[] }>(`/bots/${bot.id}/conversations/${cid}`);
      setConversationId(cid); setMsgs(d.messages.map(fromStored));
    } catch (e) { setError((e as Error).message); }
  }, [bot.id]);

  useEffect(() => { loadRecent(); }, [loadRecent]);
  useEffect(() => { if (initialConversationId) open(initialConversationId); }, [initialConversationId, open]);
  useEffect(() => { box.current?.scrollTo({ top: box.current.scrollHeight }); }, [msgs]);
  useEffect(() => () => abort.current?.abort(), []);

  async function send(e: FormEvent) {
    e.preventDefault();
    const message = q.trim();
    if (!message || busy) return;
    setQ(""); setBusy(true);
    setMsgs((m) => [...m, { role: "user", content: message }, { role: "assistant", content: "" }]);
    const patch = (fn: (last: Msg) => Msg) => setMsgs((m) => [...m.slice(0, -1), fn(m[m.length - 1])]);
    abort.current = new AbortController();
    try {
      await streamChat(`/bots/${bot.id}/chat`, { message, conversation_id: conversationId }, (ev) => {
        if (ev.type === "meta") setConversationId(ev.conversation_id);
        else if (ev.type === "token") patch((l) => ({ ...l, content: l.content + ev.text }));
        else if (ev.type === "sources") patch((l) => ({ ...l, sources: ev.items }));
        else if (ev.type === "done") patch((l) => ({ ...l, meta: ev }));
        else if (ev.type === "error") patch(() => ({ role: "error", content: ev.message }));
      }, abort.current.signal);
    } catch (err) {
      if ((err as Error).name !== "AbortError") patch(() => ({ role: "error", content: (err as Error).message }));
    } finally { setBusy(false); loadRecent(); }
  }

  return (
    <div className="card chat">
      <div className="chat-bar">
        <label className="hint" htmlFor="conv">conversation</label>
        <select id="conv" className="select" style={{ width: 340, maxWidth: "100%", height: 40 }} disabled={busy}
          value={conversationId ?? ""} onChange={(e) => open(e.target.value || null)}>
          <option value="">new conversation</option>
          {conversationId && !recent.some((c) => c.id === conversationId) && <option value={conversationId}>current conversation</option>}
          {recent.map((c) => (
            <option key={c.id} value={c.id}>{(c.title || "(untitled)").slice(0, 48)} · {fmtTime(c.last_message_at)}</option>
          ))}
        </select>
        <span style={{ flex: 1 }} />
        <button className="btn ghost sm" onClick={() => open(null)} disabled={busy || !msgs.length}>new chat</button>
      </div>
      {error && <p className="error-text" role="alert" style={{ margin: "8px 16px 0" }}>{error}</p>}

      <div className="chat-msgs" ref={box} aria-live="polite">
        {msgs.length === 0 && (
          <div className="bubble bot">{bot.greeting}<div className="hint" style={{ marginTop: 6 }}>a private test chat. answers come only from this bot&apos;s documents; questions they don&apos;t cover are declined.</div></div>
        )}
        {msgs.map((m, i) =>
          m.role === "user" ? <div key={i} className="bubble user">{m.content}</div>
          : m.role === "error" ? <div key={i} className="bubble err" role="alert">⚠ {m.content}</div>
          : (
            <div key={i} className="bubble bot">
              {m.content || <span className="typing"><span /><span /><span /></span>}
              {m.meta && (
                <div className="meta">
                  {m.meta.first_token_ms != null && <span className="chip plain">first token {m.meta.first_token_ms} ms</span>}
                  {m.meta.total_ms != null && <span className="chip plain">total {m.meta.total_ms} ms</span>}
                </div>
              )}
              {!!m.sources?.length && <Sources items={m.sources} />}
            </div>
          ))}
      </div>

      <form className="chat-form" onSubmit={send}>
        <input className="input" placeholder={bot.n_documents ? "ask something about your documents…" : "upload a document first…"} aria-label="message" maxLength={2000} value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="send" aria-label="send" disabled={busy || !q.trim()}><Arrow /></button>
      </form>
    </div>
  );
}
