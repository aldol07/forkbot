"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api, PUBLIC_API } from "@/lib/api";
import { Arrow, Star } from "./icons";

export default function Nav({ signedIn }: { signedIn: boolean }) {
  const path = usePathname();
  const router = useRouter();
  const logout = async () => { await api("/auth/logout", { method: "POST" }).catch(() => {}); router.push("/"); };
  return (
    <div className="container">
      <header className="topbar">
        <nav className="nav" aria-label="main">
          <Link href="/" className="logo"><Star />botforge</Link>
          <div className="navlinks">
            {signedIn ? (
              <>
                <Link href="/bots" className={path.startsWith("/bots") ? "active" : ""}>bots</Link>
                <a href={`${PUBLIC_API}/docs`} target="_blank" rel="noreferrer" className="hide-sm">api</a>
                <button onClick={logout}>sign out</button>
              </>
            ) : (
              <>
                <a href="#how" className="hide-sm">how it works</a>
                <a href={`${PUBLIC_API}/docs`} target="_blank" rel="noreferrer" className="hide-sm">api</a>
                <Link href="/login" className={path === "/login" ? "active" : ""}>sign in</Link>
              </>
            )}
          </div>
        </nav>
        <Link href={signedIn ? "/bots" : "/signup"} className="btn cta">
          <span>{signedIn ? <>open <b>bots</b></> : <>start <b>building</b></>}</span>
          <span className="arrow"><Arrow /></span>
        </Link>
      </header>
    </div>
  );
}
