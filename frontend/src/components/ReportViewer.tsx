"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SourceCard } from "./SourceCard";
import type { SourceInfo } from "@/types";

interface Props {
  report: string;
  bibliography: string[];
  allSources: Record<string, SourceInfo>;
  topic: string;
}

export function ReportViewer({ report, bibliography, allSources, topic }: Props) {
  const [activeTab, setActiveTab] = useState<"report" | "sources">("report");
  const [copied, setCopied] = useState(false);

  const credibleSources = Object.values(allSources).filter((s) => s.is_credible);
  const discardedSources = Object.values(allSources).filter((s) => !s.is_credible);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(report);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([report], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `research-${topic.slice(0, 30).replace(/\s+/g, "-")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const wordCount = report.split(/\s+/).filter(Boolean).length;
  const citationCount = (report.match(/\[[a-f0-9]{6,8}\]/g) || []).length;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden animate-fade-in">
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 p-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="flex bg-slate-100 dark:bg-slate-800 rounded-lg p-1 gap-1">
            {(["report", "sources"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                  activeTab === tab
                    ? "bg-white dark:bg-slate-700 shadow-sm text-slate-900 dark:text-white"
                    : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                }`}
              >
                {tab === "report" ? `📄 Report` : `🔍 Sources (${Object.keys(allSources).length})`}
              </button>
            ))}
          </div>
        </div>

        {/* Stats + actions */}
        <div className="flex items-center gap-3">
          <div className="text-xs text-slate-400 space-x-2 hidden sm:block">
            <span>{wordCount.toLocaleString()} words</span>
            <span>·</span>
            <span>{citationCount} citations</span>
            <span>·</span>
            <span>{bibliography.length} sources</span>
          </div>
          <button
            onClick={handleCopy}
            className="text-xs px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition-colors"
          >
            {copied ? "✓ Copied!" : "Copy MD"}
          </button>
          <button
            onClick={handleDownload}
            className="text-xs px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors"
          >
            ↓ Download
          </button>
        </div>
      </div>

      {/* Report tab */}
      {activeTab === "report" && (
        <div className="p-6 overflow-auto max-h-[70vh]">
          <div className="report-content max-w-4xl mx-auto">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Sources tab */}
      {activeTab === "sources" && (
        <div className="p-5 overflow-auto max-h-[70vh]">
          {/* Summary stats */}
          <div className="grid grid-cols-3 gap-3 mb-5">
            <div className="bg-emerald-50 dark:bg-emerald-950 border border-emerald-200 dark:border-emerald-800 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-emerald-700 dark:text-emerald-300">{credibleSources.length}</div>
              <div className="text-xs text-emerald-600 dark:text-emerald-400 mt-0.5">Credible Sources</div>
            </div>
            <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-red-700 dark:text-red-300">{discardedSources.length}</div>
              <div className="text-xs text-red-600 dark:text-red-400 mt-0.5">Discarded</div>
            </div>
            <div className="bg-indigo-50 dark:bg-indigo-950 border border-indigo-200 dark:border-indigo-800 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-indigo-700 dark:text-indigo-300">
                {credibleSources.length > 0
                  ? (credibleSources.reduce((acc, s) => acc + s.total_score, 0) / credibleSources.length).toFixed(1)
                  : "—"}
              </div>
              <div className="text-xs text-indigo-600 dark:text-indigo-400 mt-0.5">Avg Score</div>
            </div>
          </div>

          {/* Credible sources */}
          {credibleSources.length > 0 && (
            <>
              <h3 className="font-semibold text-sm text-slate-700 dark:text-slate-300 mb-3">
                ✓ Credible Sources (used in report)
              </h3>
              <div className="grid gap-3 sm:grid-cols-2 mb-5">
                {credibleSources
                  .sort((a, b) => b.total_score - a.total_score)
                  .map((s, i) => (
                    <SourceCard key={s.source_id} source={s} rank={i + 1} />
                  ))}
              </div>
            </>
          )}

          {/* Discarded sources */}
          {discardedSources.length > 0 && (
            <details className="mt-2">
              <summary className="cursor-pointer text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 py-2">
                ✗ Discarded Sources ({discardedSources.length}) — click to expand
              </summary>
              <div className="grid gap-3 sm:grid-cols-2 mt-3">
                {discardedSources
                  .sort((a, b) => b.total_score - a.total_score)
                  .map((s) => (
                    <SourceCard key={s.source_id} source={s} />
                  ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
