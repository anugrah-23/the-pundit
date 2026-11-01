export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let message = `Request failed (${res.status}).`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
    } catch {}
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

export type Source = { doc_id: string; kind: string; text: string; source: string };

export type AskResponse = {
  answer: string;
  cache: { hit: boolean; similarity: number | null; matched_question?: string; stored?: boolean };
  sources: Source[];
  judge: { checked: boolean; passed: boolean; score?: number; unsupported?: string[]; reason?: string; note?: string; error?: string | null } | null;
  guard: string | null;
  flagged_docs?: { doc_id: string; rules: string[] }[];
  output_blocked?: string | null;
  latency_ms: number;
  budget_exhausted?: boolean;
};

export type DebateResponse = { debate_id: number; question: string; answer_a: string; answer_b: string; sources: Source[] };
export type VoteResponse = {
  your_vote: string; judge: string; judge_orders: { A_first: string; B_first: string };
  judge_reason: string; agree: boolean; model_a: string; model_b: string;
};
export type ChallengeResponse = {
  reply: string; success: boolean; blocked_by: string | null; scan_rules: string[];
  guardrails_on: boolean; counts_for_leaderboard: boolean;
};
