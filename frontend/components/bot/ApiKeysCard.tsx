"use client";
import { useCallback, useEffect, useState } from "react";
import { api, Provider } from "@/lib/api";

type SavedKey = { provider: string; saved: boolean; last4: string | null };
type Status = { ok: boolean; text: string };

const WHERE: Record<string, { label: string; url: string }> = {
  groq: { label: "console.groq.com/keys", url: "https://console.groq.com/keys" },
  openai: { label: "platform.openai.com/api-keys", url: "https://platform.openai.com/api-keys" },
  gemini: { label: "aistudio.google.com/apikey", url: "https://aistudio.google.com/apikey" },
};

/** Account-wide LLM keys. Pasted keys are checked with the provider, stored encrypted and never shown
 *  again (only the last 4 characters). All of this account's bots use them before any server key. */
export default function ApiKeysCard({ providers, onChange }: { providers: Provider[]; onChange: () => void }) {
  const [keys, setKeys] = useState<SavedKey[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<Record<string, Status>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => api<SavedKey[]>("/keys").then(setKeys).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  async function run(provider: string, action: "test" | "save" | "remove") {
    setBusy(provider);
    const key = draft[provider]?.trim();
    try {
      if (action === "test") {
        const r = await api<{ ok: boolean; message: string }>(`/keys/${provider}/test`, { method: "POST", body: JSON.stringify(key ? { api_key: key } : {}) });
        setStatus((s) => ({ ...s, [provider]: { ok: r.ok, text: r.message } }));
      } else if (action === "save") {
        const r = await api<{ message: string }>(`/keys/${provider}`, { method: "PUT", body: JSON.stringify({ api_key: key }) });
        setDraft((d) => ({ ...d, [provider]: "" }));
        setStatus((s) => ({ ...s, [provider]: { ok: true, text: `saved · ${r.message}` } }));
      } else {
        if (!confirm(`remove your ${provider} key?`)) return;
        await api(`/keys/${provider}`, { method: "DELETE" });
        setStatus((s) => ({ ...s, [provider]: { ok: true, text: "removed" } }));
      }
      await load(); onChange();
    } catch (e) {
      setStatus((s) => ({ ...s, [provider]: { ok: false, text: (e as Error).message } }));
    } finally { setBusy(null); }
  }

  return (
    <div className="card">
      <h2 className="h2">your api keys</h2>
      <p className="muted" style={{ marginTop: 0 }}>paste your own provider keys. they&apos;re checked, stored encrypted, used by all your bots, and never shown again.</p>
      <div className="stack">
        {keys.map((k) => {
          const p = providers.find((x) => x.name === k.provider);
          const st = status[k.provider];
          const value = draft[k.provider] ?? "";
          return (
            <div key={k.provider} className="key-row">
              <div className="spread">
                <b>{k.provider}</b>
                {k.saved ? <span className="chip ok">your key ••••{k.last4}</span>
                  : p?.key_source === "server" ? <span className="chip plain">using server key</span>
                  : <span className="chip err">no key</span>}
              </div>
              <input className="input" type="password" autoComplete="off" spellCheck={false} aria-label={`${k.provider} api key`}
                placeholder={k.saved ? "paste a new key to replace it" : "paste your api key"} value={value}
                onChange={(e) => setDraft((d) => ({ ...d, [k.provider]: e.target.value }))} />
              <div className="row">
                <button className="btn ghost sm" disabled={busy === k.provider || (!value.trim() && !k.saved)} onClick={() => run(k.provider, "test")}>test</button>
                <button className="btn sm" disabled={busy === k.provider || !value.trim()} onClick={() => run(k.provider, "save")}>save</button>
                {k.saved && <button className="btn ghost sm" disabled={busy === k.provider} onClick={() => run(k.provider, "remove")}>remove</button>}
                <a className="hint" href={WHERE[k.provider].url} target="_blank" rel="noreferrer">get one: {WHERE[k.provider].label}</a>
              </div>
              {st && <span className={st.ok ? "hint" : "error-text"} role="status">{st.text}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
