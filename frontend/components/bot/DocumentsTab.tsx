"use client";
import { DragEvent, useCallback, useEffect, useRef, useState } from "react";
import { api, Bot, Doc, fmtBytes } from "@/lib/api";

const MAX_UPLOAD_MB = 25; // mirrors MAX_UPLOAD_MB on the API

export default function DocumentsTab({ bot, onChange }: { bot: Bot; onChange: () => void }) {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(() => api<Doc[]>(`/bots/${bot.id}/documents`).then(setDocs).catch((e) => setError(e.message)), [bot.id]);
  useEffect(() => { load(); }, [load]);

  // poll while anything is still being ingested
  useEffect(() => {
    if (!docs.some((d) => d.status === "pending" || d.status === "processing")) return;
    const t = setTimeout(() => { load(); onChange(); }, 1200);
    return () => clearTimeout(t);
  }, [docs, load, onChange]);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true); setError("");
    try {
      for (const f of Array.from(files)) {
        if (f.size > MAX_UPLOAD_MB * 1048576) throw new Error(`${f.name} is ${fmtBytes(f.size)}; the limit is ${MAX_UPLOAD_MB} MB`);
        const fd = new FormData();
        fd.append("file", f);
        await api(`/bots/${bot.id}/documents`, { method: "POST", body: fd });
      }
      await load();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); if (input.current) input.current.value = ""; }
  }

  async function reindex(d: Doc) {
    setError("");
    await api(`/bots/${bot.id}/documents/${d.id}/reindex`, { method: "POST" }).catch((e) => setError(e.message));
    load();
  }

  async function remove(d: Doc) {
    if (!confirm(`delete ${d.filename}?`)) return;
    await api(`/bots/${bot.id}/documents/${d.id}`, { method: "DELETE" }).catch((e) => setError(e.message));
    load(); onChange();
  }

  const onDrop = (e: DragEvent) => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files); };

  return (
    <div className="stack">
      <div
        className={`dropzone ${over ? "over" : ""}`} role="button" tabIndex={0}
        onClick={() => input.current?.click()} onKeyDown={(e) => e.key === "Enter" && input.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}
      >
        <p className="h2" style={{ margin: 0 }}>{busy ? "uploading…" : "drop files here"}</p>
        <p className="muted" style={{ margin: "4px 0 0" }}>pdf, txt or md · up to {MAX_UPLOAD_MB} mb each · or click to browse</p>
        <input ref={input} type="file" hidden multiple accept=".pdf,.txt,.md,.markdown" onChange={(e) => upload(e.target.files)} />
      </div>
      {error && <p className="error-text" role="alert">{error}</p>}
      {docs.length > 0 && (
        <div className="card" style={{ padding: 8, overflowX: "auto" }}>
          <table className="table">
            <thead><tr><th>file</th><th>size</th><th>pages</th><th>chunks</th><th>status</th><th /></tr></thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td style={{ fontWeight: 600 }}>{d.filename}</td>
                  <td className="mono">{fmtBytes(d.size_bytes)}</td>
                  <td className="mono">{d.n_pages || "–"}</td>
                  <td className="mono">{d.n_chunks}</td>
                  <td><span className={`chip ${d.status}`} title={d.error ?? ""}>{d.status}</span>{d.error && <div className="hint" style={{ marginTop: 4 }}>{d.error}</div>}</td>
                  <td>
                    <div className="row" style={{ justifyContent: "flex-end", flexWrap: "nowrap" }}>
                      {d.has_file ? (
                        <>
                          <a className="btn ghost sm" href={`/api/bots/${bot.id}/documents/${d.id}/file`} download={d.filename}>download</a>
                          <button className="btn ghost sm" onClick={() => reindex(d)} disabled={d.status === "pending" || d.status === "processing"}
                            title="re-read the stored file and rebuild its chunks">reindex</button>
                        </>
                      ) : <span className="hint" title="uploaded before files were kept; upload it again to enable download and reindex">no stored file</span>}
                      <button className="btn ghost sm" onClick={() => remove(d)}>delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
