"use client";
import { FormEvent, useState } from "react";
import { Arrow, Clip } from "@/components/icons";
import { api, Bot, PUBLIC_API } from "@/lib/api";

export default function EmbedTab({ bot, onSaved }: { bot: Bot; onSaved: (b: Bot) => void }) {
  const snippet = `<script src="${PUBLIC_API}/widget.js"\n        data-bot-id="${bot.public_id}" async></script>`;
  const [copied, setCopied] = useState(false);
  const [domains, setDomains] = useState(bot.allowed_domains.join("\n"));
  const [msg, setMsg] = useState("");

  const copy = async () => { await navigator.clipboard.writeText(snippet); setCopied(true); setTimeout(() => setCopied(false), 1500); };

  async function save(e: FormEvent) {
    e.preventDefault(); setMsg("");
    try {
      const b = await api<Bot>(`/bots/${bot.id}`, { method: "PATCH", body: JSON.stringify({ allowed_domains: domains.split(/[\n,]/) }) });
      onSaved(b); setDomains(b.allowed_domains.join("\n")); setMsg("saved");
    } catch (err) { setMsg((err as Error).message); }
  }

  return (
    <div className="two-col">
      <div className="stack">
        <div className="card">
          <h2 className="h2">1 · paste this before &lt;/body&gt;</h2>
          <div className="code">
            {snippet}
            <button className="btn sm ghost copy" style={{ color: "var(--paper)", borderColor: "rgba(242,237,223,.4)" }} onClick={copy}>{copied ? "copied" : "copy"}</button>
          </div>
          <p className="hint" style={{ marginBottom: 0 }}>optional: <span className="mono">data-position=&quot;left&quot;</span>, <span className="mono">data-open=&quot;true&quot;</span></p>
        </div>
        <div className="card">
          <h2 className="h2">2 · try it on a demo page</h2>
          <p className="muted" style={{ marginTop: 0 }}>a pretend customer site served by the api itself, so it works without adding a domain.</p>
          <a className="btn" href={`${PUBLIC_API}/demo?bot=${bot.public_id}`} target="_blank" rel="noreferrer">open demo <span className="arrow sm"><Arrow /></span></a>
        </div>
      </div>
      <form className="note" style={{ textAlign: "left" }} onSubmit={save}>
        <Clip />
        <h3>allowed domains</h3>
        <p>the widget only answers on these sites. one per line. use <span className="mono">*.example.com</span> for subdomains.</p>
        <textarea className="textarea" rows={6} value={domains} onChange={(e) => setDomains(e.target.value)} aria-label="allowed domains" />
        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn sm">save domains</button>
          {msg && <span className={msg === "saved" ? "chip ok" : "error-text"}>{msg}</span>}
        </div>
      </form>
    </div>
  );
}
