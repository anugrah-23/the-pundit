import type { Source } from "@/lib/api";

export default function Sources({ sources }: { sources: Source[] }) {
  if (!sources.length) return null;
  return (
    <details className="sources">
      <summary>Data used ({sources.length})</summary>
      {sources.map((s) => (
        <p key={s.doc_id} className="source">
          <code>{s.doc_id}</code>
          <br />
          {s.text}
        </p>
      ))}
    </details>
  );
}
