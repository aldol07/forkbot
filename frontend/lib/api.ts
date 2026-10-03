// Thin client for the FastAPI backend (same-origin via the /api rewrite).

export type User = { id: string; email: string };
export type Bot = {
  id: string; name: string; public_id: string; greeting: string; system_prompt: string;
  llm_provider: string | null; llm_model: string | null; allowed_domains: string[];
  created_at: string; n_documents: number;
};
export type Doc = {
  id: string; filename: string; content_type: string | null; size_bytes: number; status: string; error: string | null;
  n_pages: number; n_chunks: number; has_file: boolean; created_at: string;
};
export type Provider = { name: string; configured: boolean; default_model: string; is_default: boolean };
export type Source = { n: number; filename: string; page: number | null; section: string | null; kind: string; snippet: string; score: number };
export type Conversation = { id: string; source: "dashboard" | "widget"; title: string; created_at: string; last_message_at: string; n_messages: number };
export type StoredMessage = {
  id: number; role: "user" | "assistant"; content: string; sources: Source[]; provider: string | null; model: string | null;
  first_token_ms: number | null; total_ms: number | null; created_at: string;
};
export type StreamEvent =
  | { type: "meta"; conversation_id: string }
  | { type: "token"; text: string }
  | { type: "sources"; items: Source[] }
  | { type: "done"; provider: string | null; model: string | null; grounded: boolean; retrieval_ms: number; first_token_ms: number | null; total_ms: number }
  | { type: "error"; message: string };

export const PUBLIC_API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function parseError(r: Response): Promise<ApiError> {
  let msg = `request failed (${r.status})`;
  try {
    const j = await r.json();
    if (typeof j.detail === "string") msg = j.detail;
    else if (Array.isArray(j.detail)) msg = j.detail.map((d: { msg: string }) => d.msg.replace(/^Value error, /, "")).join("; ");
  } catch { /* not json */ }
  return new ApiError(r.status, msg);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isForm = init.body instanceof FormData;
  const r = await fetch(`/api${path}`, {
    ...init,
    credentials: "same-origin",
    headers: isForm ? init.headers : { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  if (!r.ok) throw await parseError(r);
  return (r.status === 204 ? undefined : await r.json()) as T;
}

/** POST and consume a Server-Sent Events stream, calling onEvent per frame. */
export async function streamChat(path: string, body: unknown, onEvent: (e: StreamEvent) => void, signal?: AbortSignal) {
  const r = await fetch(`/api${path}`, {
    method: "POST", credentials: "same-origin", signal,
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok || !r.body) throw await parseError(r);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const frames = buf.split("\n\n");
    buf = frames.pop() ?? "";
    for (const f of frames) if (f.startsWith("data: ")) onEvent(JSON.parse(f.slice(6)));
  }
}

/** "faq.pdf · p.3" / "guide.md · Setup › Install" */
export const sourceLabel = (s: Pick<Source, "filename" | "page" | "section">) =>
  [s.filename, s.page ? `p.${s.page}` : null, s.section].filter(Boolean).join(" · ");

export const fmtTime = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

export const fmtBytes = (n: number) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`);
