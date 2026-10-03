"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import Nav from "@/components/Nav";
import { Arrow, Clip } from "@/components/icons";
import { api, Bot } from "@/lib/api";
import { useUser } from "@/lib/useUser";

export default function BotsPage() {
  const { user } = useUser();
  const router = useRouter();
  const [bots, setBots] = useState<Bot[] | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => { if (user) api<Bot[]>("/bots").then(setBots).catch((e) => setError(e.message)); }, [user]);

  async function create(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      const bot = await api<Bot>("/bots", { method: "POST", body: JSON.stringify({ name }) });
      router.push(`/bots/${bot.id}`);
    } catch (err) { setError((err as Error).message); }
  }

  if (!user) return null;
  return (
    <>
      <Nav signedIn />
      <main className="container page">
        <div className="page-head">
          <div>
            <p className="kicker muted" style={{ fontSize: 18 }}>{user.email}</p>
            <h1 className="h1">your bots</h1>
          </div>
          <form className="row" onSubmit={create}>
            <input className="input" style={{ width: 260 }} placeholder="name a new bot…" aria-label="new bot name" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
            <button className="btn" disabled={!name.trim()}>create <span className="arrow sm"><Arrow /></span></button>
          </form>
        </div>
        {error && <p className="error-text">{error}</p>}

        {bots === null ? (
          <p className="muted">loading…</p>
        ) : bots.length === 0 ? (
          <div className="note" style={{ maxWidth: 420, margin: "60px auto" }}>
            <Clip />
            <h3>no bots yet</h3>
            <p>give one a name above. then upload a pdf and start chatting.</p>
          </div>
        ) : (
          <div className="grid">
            {bots.map((b) => (
              <Link key={b.id} href={`/bots/${b.id}`} className="card bot-card">
                <div className="spread"><span className="mono muted">{b.public_id}</span><span className="arrow sm" style={{ width: 30, height: 30 }}><Arrow /></span></div>
                <h3>{b.name}</h3>
                <div className="row" style={{ marginTop: "auto" }}>
                  <span className="chip plain">{b.n_documents} doc{b.n_documents === 1 ? "" : "s"}</span>
                  <span className="chip plain">{b.llm_provider ?? "default"} llm</span>
                  <span className="chip plain">{b.allowed_domains.length} domain{b.allowed_domains.length === 1 ? "" : "s"}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
