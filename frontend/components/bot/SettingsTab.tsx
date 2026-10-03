"use client";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { api, Bot, Provider } from "@/lib/api";

export default function SettingsTab({ bot, onSaved }: { bot: Bot; onSaved: (b: Bot) => void }) {
  const router = useRouter();
  const [form, setForm] = useState({
    name: bot.name, greeting: bot.greeting, system_prompt: bot.system_prompt,
    llm_provider: bot.llm_provider ?? "", llm_model: bot.llm_model ?? "",
  });
  const [providers, setProviders] = useState<Provider[]>([]);
  const [msg, setMsg] = useState("");
  useEffect(() => { api<Provider[]>("/providers").then(setProviders).catch(() => {}); }, []);
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  async function save(e: FormEvent) {
    e.preventDefault(); setMsg("");
    try {
      const b = await api<Bot>(`/bots/${bot.id}`, {
        method: "PATCH",
        body: JSON.stringify({ ...form, llm_provider: form.llm_provider || null, llm_model: form.llm_model || null }),
      });
      onSaved(b); setMsg("saved");
    } catch (err) { setMsg((err as Error).message); }
  }

  async function remove() {
    if (!confirm(`delete "${bot.name}" and all its documents? this can't be undone.`)) return;
    await api(`/bots/${bot.id}`, { method: "DELETE" });
    router.push("/bots");
  }

  return (
    <div className="two-col">
      <form className="card" onSubmit={save}>
        <h2 className="h2">bot settings</h2>
        <div className="field"><label htmlFor="n">name</label><input id="n" className="input" maxLength={80} required value={form.name} onChange={set("name")} /></div>
        <div className="field"><label htmlFor="g">greeting</label><input id="g" className="input" maxLength={300} value={form.greeting} onChange={set("greeting")} /></div>
        <div className="field">
          <label htmlFor="sp">extra instructions</label>
          <textarea id="sp" className="textarea" maxLength={4000} placeholder="e.g. answer in a friendly tone, always mention our support email" value={form.system_prompt} onChange={set("system_prompt")} />
        </div>
        <div className="row" style={{ alignItems: "flex-start" }}>
          <div className="field" style={{ flex: 1, minWidth: 160 }}>
            <label htmlFor="p">llm provider</label>
            <select id="p" className="select" value={form.llm_provider} onChange={set("llm_provider")}>
              <option value="">server default</option>
              {providers.map((p) => <option key={p.name} value={p.name}>{p.name}{p.configured ? "" : " (no key)"}</option>)}
            </select>
          </div>
          <div className="field" style={{ flex: 1, minWidth: 160 }}>
            <label htmlFor="m">model</label>
            <input id="m" className="input" placeholder={providers.find((p) => p.name === form.llm_provider)?.default_model ?? "provider default"} value={form.llm_model} onChange={set("llm_model")} />
          </div>
        </div>
        <div className="row"><button className="btn">save</button>{msg && <span className={msg === "saved" ? "chip ok" : "error-text"}>{msg}</span>}</div>
      </form>
      <div className="stack">
        <div className="card">
          <h2 className="h2">providers on this server</h2>
          <table className="table">
            <tbody>
              {providers.map((p) => (
                <tr key={p.name}>
                  <td style={{ fontWeight: 600 }}>{p.name}{p.is_default && <span className="hint"> · default</span>}</td>
                  <td className="mono">{p.default_model}</td>
                  <td><span className={`chip ${p.configured ? "ok" : "err"}`}>{p.configured ? "ready" : "no key"}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="hint" style={{ marginBottom: 0 }}>add keys in <span className="mono">botforge/.env</span> and restart the api.</p>
        </div>
        <div className="card">
          <h2 className="h2">danger zone</h2>
          <button className="btn danger" onClick={remove}>delete this bot</button>
        </div>
      </div>
    </div>
  );
}
