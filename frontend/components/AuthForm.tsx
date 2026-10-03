"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import Nav from "@/components/Nav";
import { Clip } from "@/components/icons";
import { api } from "@/lib/api";

export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const signup = mode === "signup";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api(`/auth/${mode}`, { method: "POST", body: JSON.stringify({ email, password }) });
      router.push("/bots");
    } catch (err) {
      setError((err as Error).message);
    } finally { setBusy(false); }
  }

  return (
    <>
      <Nav signedIn={false} />
      <main className="container auth-wrap">
        <form className="note auth-card" onSubmit={submit}>
          <Clip />
          <h3 style={{ fontSize: 28, fontWeight: 800 }}>{signup ? "make an account" : "welcome back"}</h3>
          <p>{signup ? "your first bot is two minutes away" : "sign in to manage your bots"}</p>
          <div className="field">
            <label htmlFor="email">email</label>
            <input id="email" className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="pw">password</label>
            <input id="pw" className="input" type="password" autoComplete={signup ? "new-password" : "current-password"} required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            {signup && <span className="hint">at least 8 characters</span>}
          </div>
          {error && <p className="error-text" role="alert">{error}</p>}
          <button className="btn" style={{ width: "100%" }} disabled={busy}>{busy ? "one sec…" : signup ? "create account" : "sign in"}</button>
          <p style={{ marginTop: 16, marginBottom: 0, fontSize: 14 }}>
            {signup ? <>already have one? <Link href="/login">sign in</Link></> : <>new here? <Link href="/signup">make an account</Link></>}
          </p>
        </form>
      </main>
    </>
  );
}
