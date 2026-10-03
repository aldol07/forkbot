"use client";
import { useCallback, useEffect, useState } from "react";
import Sources from "@/components/bot/Sources";
import { api, Bot, Conversation, fmtTime, StoredMessage } from "@/lib/api";

type Filter = "all" | "widget" | "dashboard";

export default function HistoryTab({ bot, onContinue }: { bot: Bot; onContinue: (conversationId: string) => void }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [convs, setConvs] = useState<Conversation[] | null>(null);
  const [open, setOpen] = useState<{ conversation: Conversation; messages: StoredMessage[] } | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    const q = filter === "all" ? "" : `?source=${filter}`;
    return api<Conversation[]>(`/bots/${bot.id}/conversations${q}`).then(setConvs).catch((e) => setError(e.message));
  }, [bot.id, filter]);
  useEffect(() => { load(); }, [load]);

  const show = (c: Conversation) =>
    api<{ conversation: Conversation; messages: StoredMessage[] }>(`/bots/${bot.id}/conversations/${c.id}`)
      .then(setOpen).catch((e) => setError(e.message));

  async function remove(c: Conversation) {
    if (!confirm("delete this conversation?")) return;
    await api(`/bots/${bot.id}/conversations/${c.id}`, { method: "DELETE" }).catch((e) => setError(e.message));
    if (open?.conversation.id === c.id) setOpen(null);
    load();
  }

  return (
    <div className="stack">
      <div className="row">
        {(["all", "widget", "dashboard"] as Filter[]).map((f) => (
          <button key={f} className={`btn sm ${filter === f ? "" : "ghost"}`} onClick={() => { setFilter(f); setOpen(null); }}>{f}</button>
        ))}
        <span style={{ flex: 1 }} />
        <button className="btn ghost sm" onClick={load}>refresh</button>
      </div>
      {error && <p className="error-text" role="alert">{error}</p>}
      {convs && convs.length === 0 && (
        <div className="card empty"><p className="muted" style={{ margin: 0 }}>no conversations yet. chat in the chat tab or on your site and they&apos;ll show up here.</p></div>
      )}
      {!!convs?.length && (
        <div className="history">
          <div className="card history-list">
            {convs.map((c) => (
              <button key={c.id} className={`history-item ${open?.conversation.id === c.id ? "active" : ""}`} onClick={() => show(c)}>
                <span className="history-title">{c.title || "(untitled)"}</span>
                <span className="row" style={{ gap: 6 }}>
                  <span className={`chip ${c.source === "widget" ? "ok" : "plain"}`}>{c.source}</span>
                  <span className="hint">{c.n_messages} msgs · {fmtTime(c.last_message_at)}</span>
                </span>
              </button>
            ))}
          </div>
          <div className="card chat-msgs history-view">
            {!open && <p className="muted" style={{ margin: "auto" }}>pick a conversation</p>}
            {open && (
              <>
                <div className="spread" style={{ alignSelf: "stretch" }}>
                  <span className="hint">started {fmtTime(open.conversation.created_at)} · {open.conversation.source}</span>
                  <span className="row" style={{ gap: 8 }}>
                    {open.conversation.source === "dashboard"
                      ? <button className="btn sm" onClick={() => onContinue(open.conversation.id)}>continue in chat</button>
                      : <span className="hint">visitor chat · read only</span>}
                    <button className="btn ghost sm" onClick={() => remove(open.conversation)}>delete</button>
                  </span>
                </div>
                {open.messages.map((m) => m.role === "user"
                  ? <div key={m.id} className="bubble user">{m.content}</div>
                  : (
                    <div key={m.id} className="bubble bot">
                      {m.content}
                      <div className="meta">
                        {m.first_token_ms != null && <span className="chip plain">first token {m.first_token_ms} ms</span>}
                        {m.total_ms != null ? <span className="chip plain">total {m.total_ms} ms</span> : <span className="chip plain">interrupted</span>}
                      </div>
                      {!!m.sources?.length && <Sources items={m.sources} />}
                    </div>
                  ))}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
