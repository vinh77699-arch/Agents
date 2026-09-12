"use client";
import { type SourceInfo } from "@/types";

function ScoreBadge({ score }: { score: number }) {
  const cls = score >= 7 ? "score-high" : score >= 5 ? "score-medium" : "score-low";
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${cls}`}>
      {score.toFixed(1)}
    </span>
  );
}

function ScoreBar({ label, value, max = 10 }: { label: string; value: number; max?: number }) {
  const pct = Math.min(100, (value / max) * 100);
  const color = pct >= 70 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-slate-500 dark:text-slate-400 text-right flex-shrink-0">{label}</span>
      <div className="flex-1 bg-slate-100 dark:bg-slate-700 rounded-full h-1.5">
        <div className={`h-1.5 rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-slate-600 dark:text-slate-400 font-medium">{value.toFixed(1)}</span>
    </div>
  );
}

interface Props {
  source: SourceInfo;
  rank?: number;
}

export function SourceCard({ source, rank }: Props) {
  const domain = (() => {
    try { return new URL(source.url).hostname; }
    catch { return source.url?.slice(0, 30) || "unknown"; }
  })();

  return (
    <div className={`bg-white dark:bg-slate-900 rounded-lg border p-4 shadow-sm hover:shadow-md transition-shadow ${
      source.is_credible
        ? "border-emerald-200 dark:border-emerald-800"
        : "border-red-200 dark:border-red-900 opacity-70"
    }`}>
      <div className="flex items-start gap-3">
        {rank && (
          <span className="flex-shrink-0 w-6 h-6 bg-slate-100 dark:bg-slate-800 rounded-full text-xs flex items-center justify-center font-bold text-slate-500">
            {rank}
          </span>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-sm text-indigo-600 dark:text-indigo-400 hover:underline line-clamp-1"
              >
                {source.title || domain}
              </a>
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{domain}</p>
            </div>
            <ScoreBadge score={source.total_score} />
          </div>

          {/* Score breakdown */}
          <div className="mt-3 space-y-1.5">
            <ScoreBar label="Domain" value={source.domain_score} />
            <ScoreBar label="Recency" value={source.recency_score} />
            <ScoreBar label="Cross-ref" value={source.cross_ref_score} />
            <ScoreBar label="Quality" value={source.llm_judge_score} />
          </div>

          {/* Explanation */}
          {source.explanation && (
            <p className="mt-3 text-xs text-slate-500 dark:text-slate-400 italic line-clamp-2">
              {source.explanation}
            </p>
          )}

          <div className="mt-2 flex items-center gap-2">
            {source.is_credible ? (
              <span className="text-xs bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 px-2 py-0.5 rounded-full">
                ✓ Credible
              </span>
            ) : (
              <span className="text-xs bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300 px-2 py-0.5 rounded-full">
                ✗ Discarded
              </span>
            )}
            {source.published_date && (
              <span className="text-xs text-slate-400">{source.published_date}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
