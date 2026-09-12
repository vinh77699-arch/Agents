"use client";
import { type AgentState } from "@/types";

const AGENT_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  planner: { label: "Planner Agent", icon: "🗺️", color: "indigo" },
  searcher: { label: "Search & Scraper Agent", icon: "🔍", color: "blue" },
  credibility: { label: "Credibility Evaluator", icon: "⭐", color: "amber" },
  synthesizer: { label: "Synthesis Agent (RAG)", icon: "🧬", color: "emerald" },
  report_writer: { label: "Report Writer Agent", icon: "📝", color: "purple" },
  pipeline: { label: "Pipeline Controller", icon: "⚙️", color: "gray" },
};

const STATUS_COLORS: Record<string, string> = {
  pending: "border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500",
  running: "border-indigo-400 dark:border-indigo-500 text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950",
  completed: "border-emerald-400 dark:border-emerald-600 text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950",
  failed: "border-red-400 dark:border-red-600 text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-950",
  retrying: "border-amber-400 dark:border-amber-600 text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950",
};

interface Props {
  agents: AgentState[];
  isRunning: boolean;
  searchCallsUsed?: number;
  retryCount?: number;
}

export function PipelineProgress({ agents, isRunning, searchCallsUsed = 0, retryCount = 0 }: Props) {
  const completedCount = agents.filter((a) => a.status === "completed").length;
  const progress = (completedCount / agents.length) * 100;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <span>Pipeline Progress</span>
          {isRunning && (
            <span className="inline-flex items-center gap-1 text-xs bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 px-2 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-pulse" />
              Running
            </span>
          )}
        </h2>
        <div className="text-xs text-slate-500 dark:text-slate-400 space-x-3">
          <span>Calls: {searchCallsUsed}/15</span>
          {retryCount > 0 && <span className="text-amber-600">Retry #{retryCount}</span>}
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2 mb-5">
        <div
          className="bg-gradient-to-r from-indigo-500 to-purple-500 h-2 rounded-full transition-all duration-700"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Agent steps */}
      <div className="space-y-2">
        {agents.map((agent, idx) => {
          const config = AGENT_CONFIG[agent.name] || { label: agent.name, icon: "🤖", color: "gray" };
          const statusClass = STATUS_COLORS[agent.status] || STATUS_COLORS.pending;
          const isActive = agent.status === "running" || agent.status === "retrying";

          return (
            <div
              key={agent.name}
              className={`flex items-start gap-3 p-3 rounded-lg border transition-all duration-300 ${statusClass} animate-fade-in`}
            >
              {/* Step number + icon */}
              <div className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-white dark:bg-slate-800 border border-current text-sm font-bold">
                {agent.status === "completed" ? "✓" : agent.status === "failed" ? "✗" : idx + 1}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-base">{config.icon}</span>
                  <span className="font-medium text-sm truncate">{config.label}</span>
                  {isActive && (
                    <div className="flex gap-0.5 ml-1">
                      {[0, 1, 2].map((i) => (
                        <div
                          key={i}
                          className="w-1 h-1 rounded-full bg-current opacity-60 animate-bounce"
                          style={{ animationDelay: `${i * 0.15}s` }}
                        />
                      ))}
                    </div>
                  )}
                </div>
                {agent.message && (
                  <p className="text-xs mt-1 opacity-80 truncate">{agent.message}</p>
                )}
                {/* Extra data badges */}
                {agent.data && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {Object.entries(agent.data).map(([k, v]) => (
                      <span
                        key={k}
                        className="text-xs bg-white/60 dark:bg-slate-800/60 px-1.5 py-0.5 rounded border border-current/20"
                      >
                        {k}: <strong>{String(v)}</strong>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Status badge */}
              <span className="flex-shrink-0 text-xs font-medium capitalize px-2 py-0.5 rounded bg-white/60 dark:bg-slate-800/60">
                {agent.status}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
