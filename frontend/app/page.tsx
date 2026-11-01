"use client";

import { FormEvent, useState } from "react";
import ScoreBug from "@/components/ScoreBug";
import Sources from "@/components/Sources";
import { api, type AskResponse } from "@/lib/api";

const EXAMPLES = [
  "Who leads the Premier League in xG?",
  "Bayern ka PPDA kitna hai is season?",
  "Mbappe evlo goals adichirukaan?",
  "What does a false nine do?",
];

type Turn = { question: string; response?: AskResponse; error?: string };

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);

  async function ask(q: string) {
    const text = q.trim();
    if (text.length < 2 || busy) return;
    setBusy(true);
    setQuestion("");
    setTurns((t) => [{ question: text }, ...t]);
    try {
      const response = await api<AskResponse>("/api/ask", { question: text });
      setTurns((t) => [{ question: text, response }, ...t.slice(1)]);
    } catch (e) {
      setTurns((t) => [{ question: text, error: (e as Error).message }, ...t.slice(1)]);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    ask(question);
  }

  return (
    <>
      <h1>Ask the Pundit</h1>
      <p className="lede">
        Stats questions on the Premier League, La Liga, Serie A, Bundesliga and Ligue 1, answered only from real 2026-27
        data. Ask in English, Hinglish or Tanglish. Repeat questions come back instantly from the cache.
      </p>
      <form onSubmit={onSubmit} className="field">
        <input
          className="input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="How many goals has Haaland scored this season?"
          maxLength={300}
          aria-label="Your question"
        />
        <button className="btn" disabled={busy || question.trim().length < 2}>
          {busy ? "Asking" : "Ask"}
        </button>
      </form>
      <div className="chips">
        {EXAMPLES.map((ex) => (
          <button key={ex} className="chip" type="button" onClick={() => ask(ex)} disabled={busy}>
            {ex}
          </button>
        ))}
      </div>

      <div className="thread" aria-live="polite">
        {turns.map((t, i) => (
          <article className="turn" key={turns.length - i}>
            <p className="q">{t.question}</p>
            {!t.response && !t.error && <p className="muted">Checking the cache and the stats…</p>}
            {t.error && <p className="error">{t.error}</p>}
            {t.response && (
              <div className="answer">
                <p>{t.response.answer}</p>
                <ScoreBug r={t.response} />
                {t.response.output_blocked && (
                  <p className="note">
                    <span className="ref-card red" aria-hidden />
                    The original reply was blocked by the output check ({t.response.output_blocked.replace("_", " ")}).
                  </p>
                )}
                {!!t.response.flagged_docs?.length && (
                  <p className="note">
                    <span className="ref-card yellow" aria-hidden />
                    {t.response.flagged_docs.length} retrieved document(s) looked like an injection attempt and were dropped.
                  </p>
                )}
                {t.response.cache.hit && t.response.cache.matched_question && (
                  <p className="note">Matched the earlier question: “{t.response.cache.matched_question}”</p>
                )}
                <Sources sources={t.response.sources} />
              </div>
            )}
          </article>
        ))}
      </div>
    </>
  );
}
