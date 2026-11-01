"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Live = {
  ask: {
    requests: number; cache_hits: number; hit_rate: number | null; llm_calls_saved: number;
    avg_latency_hit_ms: number; avg_latency_miss_ms: number; guard_skips: Record<string, number>;
    judge_checked: number; judge_pass_rate: number | null; outputs_blocked: number; docs_flagged: number; cache_size: number;
  };
  debate: { votes: number; agreement: number | null; kappa: number | null };
  challenge: { attempts_guarded: number; successes_guarded: number; attempts_unguarded: number; successes_unguarded: number };
  data_version: string; llm_calls_today: number; daily_budget: number;
};
type SweepRow = { threshold: number; guards: boolean; hit_rate: number | null; hits: number; false_hits: number; llm_calls_avoided_pct: number };
type Offline = {
  cache_sweep?: { embedder: string; n_tests: number; rows: SweepRow[] };
  injection_suite?: { attacks: { id: string; type: string; worked_before: boolean; worked_after: boolean; stopped_by: string | null }[]; before: number; after: number; n: number; false_blocks: number; n_normal: number };
  judge_audit?: { n: number; naive_agreement: number; naive_kappa: number | null; position_flips: number; length_bias_moves_of_10: number; self_judge_picks_own: number; human_picks_second: number; fixed_agreement: number; fixed_kappa: number | null };
};

const pct = (x: number | null | undefined) => (x === null || x === undefined ? "–" : `${Math.round(x * 100)}%`);

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="stat">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export default function NumbersPage() {
  const [data, setData] = useState<{ live: Live; offline: Offline } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ live: Live; offline: Offline }>("/api/numbers").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">Loading the numbers…</p>;
  const { live, offline } = data;
  const guardSkips = Object.values(live.ask.guard_skips).reduce((a, b) => a + b, 0);

  return (
    <>
      <h1>The numbers</h1>
      <p className="lede">
        Everything on this page is measured, not claimed. The live figures come from real traffic on this site; the
        tables below come from fixed test sets that can be re-run from the repository. Data version {live.data_version}.
      </p>

      <section>
        <h2>Cache</h2>
        <dl className="stat-list">
          <Stat label="Questions answered" value={live.ask.requests} />
          <Stat label="Served from cache" value={pct(live.ask.hit_rate)} />
          <Stat label="Average time, cached" value={`${Math.round(live.ask.avg_latency_hit_ms)} ms`} />
          <Stat label="Average time, fresh" value={`${Math.round(live.ask.avg_latency_miss_ms)} ms`} />
          <Stat label="Wrong reuses stopped by guards" value={guardSkips} />
          <Stat label="Answers in the cache" value={live.ask.cache_size} />
        </dl>
        {offline.cache_sweep && (
          <>
            <h3>Threshold sweep on {offline.cache_sweep.n_tests} labelled questions</h3>
            <div className="table-scroll">
              <table>
                <thead><tr><th>Guards</th><th className="num">Threshold</th><th className="num">Hit rate</th><th className="num">False hits</th><th className="num">LLM calls avoided</th></tr></thead>
                <tbody>
                  {offline.cache_sweep.rows.map((r) => (
                    <tr key={`${r.guards}-${r.threshold}`}>
                      <td>{r.guards ? "On" : "Off"}</td><td className="num">{r.threshold.toFixed(2)}</td><td className="num">{pct(r.hit_rate)}</td>
                      <td className="num">{r.false_hits}</td><td className="num">{r.llm_calls_avoided_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <section>
        <h2>Judge</h2>
        <dl className="stat-list">
          <Stat label="Fresh answers checked" value={live.ask.judge_checked} />
          <Stat label="Passed the faithfulness check" value={pct(live.ask.judge_pass_rate)} />
          <Stat label="Debate votes" value={live.debate.votes} />
          <Stat label="Visitors agree with the judge" value={pct(live.debate.agreement)} />
          <Stat label="Cohen's kappa" value={live.debate.kappa ?? "–"} />
        </dl>
        {offline.judge_audit && (
          <div className="table-scroll">
            <table>
              <thead><tr><th>Bias test on {offline.judge_audit.n} hand-graded pairs</th><th className="num">Result</th></tr></thead>
              <tbody>
                <tr><td>Agreement with human grades, naive judge</td><td className="num">{offline.judge_audit.naive_agreement}/{offline.judge_audit.n}</td></tr>
                <tr><td>Verdicts that flipped when answer order was swapped</td><td className="num">{offline.judge_audit.position_flips}</td></tr>
                <tr><td>Verdicts that moved toward a padded answer (of 10)</td><td className="num">{offline.judge_audit.length_bias_moves_of_10}</td></tr>
                <tr><td>Times a model judging itself picked its own answer (human picked it {offline.judge_audit.human_picks_second})</td><td className="num">{offline.judge_audit.self_judge_picks_own}</td></tr>
                <tr><td>Agreement after fixes (both orders, length rule, different family)</td><td className="num">{offline.judge_audit.fixed_agreement}/{offline.judge_audit.n}</td></tr>
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2>Guardrails</h2>
        <dl className="stat-list">
          <Stat label="Attacks with guardrails on" value={live.challenge.attempts_guarded} />
          <Stat label="Got through" value={live.challenge.successes_guarded} />
          <Stat label="Attacks with guardrails off" value={live.challenge.attempts_unguarded} />
          <Stat label="Got through" value={live.challenge.successes_unguarded} />
        </dl>
        {offline.injection_suite && (
          <>
            <p>
              Successful injections: {offline.injection_suite.before}/{offline.injection_suite.n} before guardrails,{" "}
              {offline.injection_suite.after}/{offline.injection_suite.n} after; {offline.injection_suite.false_blocks} false blocks on{" "}
              {offline.injection_suite.n_normal} normal questions.
            </p>
            <div className="table-scroll">
              <table>
                <thead><tr><th>Attack</th><th>Worked before</th><th>Worked after</th><th>Stopped by</th></tr></thead>
                <tbody>
                  {offline.injection_suite.attacks.map((a) => (
                    <tr key={a.id}><td>{a.type.replaceAll("_", " ")}</td><td>{a.worked_before ? "Yes" : "No"}</td><td>{a.worked_after ? "Yes" : "No"}</td><td>{a.stopped_by?.replace("output_check:", "output check: ") ?? "–"}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        <p className="note">No single defence fully stops prompt injection. The Pundit uses layers and measures each one.</p>
      </section>

      <p className="note">Model calls today: {live.llm_calls_today} of a {live.daily_budget} daily budget.</p>
    </>
  );
}
