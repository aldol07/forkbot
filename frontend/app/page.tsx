"use client";
import Link from "next/link";
import { useState } from "react";
import Nav from "@/components/Nav";
import { ROBOT } from "@/components/art";
import { Arrow, Clip, Wave } from "@/components/icons";
import { useUser } from "@/lib/useUser";

const STEPS = [
  ["01", "upload", "drop in pdfs, faqs or markdown. we chunk, embed and index them in postgres + pgvector."],
  ["02", "test", "chat with your bot, switch between groq, openai, gemini or ollama, and watch first-token latency."],
  ["03", "embed", "paste one script tag on your site. only the domains you allow can use it."],
];

export default function Home() {
  const { user } = useUser(false);
  const [note, setNote] = useState(true);
  return (
    <>
      <Nav signedIn={!!user} />
      <main className="container">
        <section className="hero">
          {note && (
            <div className="note tilt hero-note">
              <Clip />
              <button className="x" aria-label="dismiss" onClick={() => setNote(false)}>×</button>
              <h3>new: provider testing</h3>
              <p>compare groq, openai, gemini and local models on the same question</p>
              <div style={{ color: "var(--ink)", margin: "4px 0 14px" }}><Wave /></div>
              <Link href={user ? "/bots" : "/signup"} className="btn sm" style={{ width: "100%" }}>try it</Link>
            </div>
          )}
          <div>
            <p className="kicker">we build chatbots from your documents</p>
            <h1 className="display">your docs,<br />now a chatbot</h1>
            <p className="lead">multi-tenant, document-grounded ai assistants with hybrid search, streaming answers and a one-line embeddable widget.</p>
            <Link href={user ? "/bots" : "/signup"} className="btn cta">
              <span>{user ? <>go to <b>your bots</b></> : <>make your <b>first bot</b></>}</span>
              <span className="arrow"><Arrow /></span>
            </Link>
          </div>
          <div className="hero-art"><pre className="ascii" aria-hidden="true">{ROBOT}</pre></div>
        </section>

        <section id="how" style={{ padding: "40px 0 100px" }}>
          <p className="kicker">how it works</p>
          <div className="grid" style={{ marginTop: 20 }}>
            {STEPS.map(([n, t, d]) => (
              <div className="card" key={n}>
                <div className="mono muted">{n}</div>
                <h3 className="h2" style={{ marginTop: 6 }}>{t}</h3>
                <p className="muted" style={{ margin: 0 }}>{d}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
      <footer className="container footer credit">
        forkbot · built by <a href="mailto:dubeykartikay13@gmail.com?subject=forkbot" title="contact: dubeykartikay13@gmail.com">aldol</a>
      </footer>
    </>
  );
}
