"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Nav from "@/components/Nav";
import ChatTab from "@/components/bot/ChatTab";
import DocumentsTab from "@/components/bot/DocumentsTab";
import EmbedTab from "@/components/bot/EmbedTab";
import SettingsTab from "@/components/bot/SettingsTab";
import { api, Bot } from "@/lib/api";
import { useUser } from "@/lib/useUser";

const TABS = ["documents", "chat", "embed", "settings"] as const;
type Tab = (typeof TABS)[number];

export default function BotPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useUser();
  const [bot, setBot] = useState<Bot | null>(null);
  const [tab, setTab] = useState<Tab>("documents");
  const [error, setError] = useState("");

  const reload = useCallback(() => api<Bot>(`/bots/${id}`).then(setBot).catch((e) => setError(e.message)), [id]);
  useEffect(() => { if (user) reload(); }, [user, reload]);
  useEffect(() => {
    const h = window.location.hash.slice(1) as Tab;
    if (TABS.includes(h)) setTab(h);
  }, []);
  const pick = (t: Tab) => { setTab(t); history.replaceState(null, "", `#${t}`); };

  if (!user) return null;
  return (
    <>
      <Nav signedIn />
      <main className="container page">
        <Link href="/bots" className="muted" style={{ textDecoration: "none" }}>← all bots</Link>
        {error && <p className="error-text">{error}</p>}
        {bot && (
          <>
            <div className="page-head" style={{ marginTop: 10 }}>
              <h1 className="h1">{bot.name}</h1>
              <span className="chip plain">{bot.public_id}</span>
            </div>
            <div className="tabs" role="tablist">
              {TABS.map((t) => (
                <button key={t} role="tab" aria-selected={tab === t} className="tab" onClick={() => pick(t)}>{t}</button>
              ))}
            </div>
            {tab === "documents" && <DocumentsTab bot={bot} onChange={reload} />}
            {tab === "chat" && <ChatTab bot={bot} />}
            {tab === "embed" && <EmbedTab bot={bot} onSaved={setBot} />}
            {tab === "settings" && <SettingsTab bot={bot} onSaved={setBot} />}
          </>
        )}
      </main>
    </>
  );
}
