import type { AskResponse } from "@/lib/api";

const GUARD_TEXT: Record<string, string> = {
  "entity:players": "Similar question in the cache was about a different player, so it was skipped.",
  "entity:teams": "Similar question in the cache was about a different team, so it was skipped.",
  "entity:competitions": "Similar question in the cache was about a different competition, so it was skipped.",
  "entity:seasons": "Similar question in the cache was about a different season, so it was skipped.",
  negation: "Similar question in the cache had the opposite meaning (a negation), so it was skipped.",
  expired: "The cached answer was from before the latest data refresh, so it was skipped.",
};

/** Broadcast-style score bug: cache state, similarity and response time. */
export default function ScoreBug({ r }: { r: AskResponse }) {
  const sim = r.cache.similarity;
  return (
    <div className="meta-row">
      <span className="bug" aria-label={`${r.cache.hit ? "Cache hit" : "Cache miss"}, ${Math.round(r.latency_ms)} milliseconds`}>
        <span className={`bug-state${r.cache.hit ? " hit" : ""}`}>{r.cache.hit ? "Cache hit" : "Fresh answer"}</span>
        {sim !== null && sim !== undefined && <span className="bug-num">sim {sim.toFixed(2)}</span>}
        <span className="bug-num">{Math.round(r.latency_ms)} ms</span>
      </span>
      {r.judge?.checked && !r.cache.hit && (
        <span className="note">{r.judge.passed ? `Judge: faithful to the data (${r.judge.score}/5)` : "Judge: not fully supported by the data, so not cached"}</span>
      )}
      {r.cache.hit && <span className="note">Checked by the judge when first cached</span>}
      {r.guard && GUARD_TEXT[r.guard] && <span className="note">{GUARD_TEXT[r.guard]}</span>}
    </div>
  );
}
