"use client";

import { useEffect, useState } from "react";
import Sources from "@/components/Sources";
import { api, type DebateResponse, type VoteResponse } from "@/lib/api";

const WINNER_TEXT: Record<string, string> = { A: "Pundit A", B: "Pundit B", tie: "a tie" };

export default function DebatePage() {
  const [questions, setQuestions] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [debate, setDebate] = useState<DebateResponse | null>(null);
  const [verdict, setVerdict] = useState<VoteResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<string[]>("/api/debate/questions").then(setQuestions).catch(() => {});
  }, []);

  async function start(q: string) {
    if (q.trim().length < 2) return;
    setBusy(true);
    setError("");
    setDebate(null);
    setVerdict(null);
    try {
      setDebate(await api<DebateResponse>("/api/debate", { question: q.trim() }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function vote(v: "A" | "B" | "tie") {
    if (!debate) return;
    try {
      setVerdict(await api<VoteResponse>(`/api/debate/${debate.debate_id}/vote`, { vote: v }));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      <h1>Pundit Debate</h1>
      <p className="lede">
        Two AI models answer the same question from the same stats. Pick the better answer before you see who they are
        and what the AI judge thought. Every vote helps measure how far an AI judge can be trusted.
      </p>

      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          start(question);
        }}
      >
        <div>
          <label htmlFor="pick">Pick a question</label>
          <select id="pick" className="select" value="" onChange={(e) => { setQuestion(e.target.value); start(e.target.value); }} disabled={busy}>
            <option value="" disabled>Choose one of {questions.length} questions</option>
            {questions.map((q) => <option key={q} value={q}>{q}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="own">Or ask your own</label>
          <div className="field">
            <input id="own" className="input" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={300} placeholder="Is Arsenal's press better than Liverpool's?" />
            <button className="btn" disabled={busy || question.trim().length < 2}>{busy ? "Debating" : "Start debate"}</button>
          </div>
        </div>
      </form>
      {error && <p className="error">{error}</p>}
      {busy && <p className="muted">Both pundits are reading the stats…</p>}

      {debate && (
        <section aria-live="polite">
          <h2 style={{ marginTop: 32 }}>{debate.question}</h2>
          <div className="versus">
            {(["A", "B"] as const).map((side) => (
              <div key={side} className={`pundit${verdict && verdict.your_vote === side ? " won" : ""}`}>
                <h3>Pundit {side}{verdict && <span className="muted small"> ({side === "A" ? verdict.model_a : verdict.model_b})</span>}</h3>
                <p>{side === "A" ? debate.answer_a : debate.answer_b}</p>
                {!verdict && <button className="btn" onClick={() => vote(side)}>Pundit {side} is better</button>}
              </div>
            ))}
          </div>
          {!verdict && <p><button className="btn ghost" onClick={() => vote("tie")}>It's a tie</button></p>}
          {verdict && (
            <div className="verdict">
              <h3>{verdict.agree ? "You and the judge agree" : "You and the judge disagree"}</h3>
              <p>
                You picked {WINNER_TEXT[verdict.your_vote]}. The judge picked {WINNER_TEXT[verdict.judge]}
                {verdict.judge === "tie" && verdict.judge_orders.A_first !== verdict.judge_orders.B_first
                  ? ", because its choice changed when the answers were shown in the opposite order"
                  : ""}
                .
              </p>
              {verdict.judge_reason && <p className="muted">{verdict.judge_reason}</p>}
              <p className="note">
                The judge sees each pair twice, in both orders, and a win only counts if it holds both times. This
                removes position bias.
              </p>
            </div>
          )}
          <Sources sources={debate.sources} />
        </section>
      )}
    </>
  );
}
