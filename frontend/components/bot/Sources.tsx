import { Source, sourceLabel } from "@/lib/api";

/** Retrieved passages grouped by file: "3 passages from 2 files", then one block per file. */
export default function Sources({ items }: { items: Source[] }) {
  if (!items.length) return null;
  const byFile = new Map<string, Source[]>();
  for (const s of items) byFile.set(s.filename, [...(byFile.get(s.filename) ?? []), s]);
  const nFiles = byFile.size;
  return (
    <details className="sources">
      <summary>
        {items.length} passage{items.length > 1 ? "s" : ""} from {nFiles} file{nFiles > 1 ? "s" : ""}
      </summary>
      {[...byFile.entries()].map(([file, passages]) => (
        <div key={file} className="source-file">
          <b>{file}</b>
          <ol>
            {passages.map((s) => (
              <li key={s.n} value={s.n}>
                <span className="mono">{sourceLabel({ ...s, filename: "" }).replace(/^ · /, "") || "passage"}</span>{" "}
                {s.snippet.replace(/\s+/g, " ")}…
              </li>
            ))}
          </ol>
        </div>
      ))}
    </details>
  );
}
