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

type Tab = "report" | "vietnamese" | "sources";

export function ReportViewer({ report, bibliography, allSources, topic }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("report");
  const [copied, setCopied] = useState(false);
  const [viReport, setViReport] = useState<string>("");
  const [translating, setTranslating] = useState(false);
  const [translateError, setTranslateError] = useState<string>("");

  const credibleSources = Object.values(allSources).filter((s) => s.is_credible);
  const discardedSources = Object.values(allSources).filter((s) => !s.is_credible);

  const activeContent = activeTab === "vietnamese" ? viReport : report;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(activeContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const suffix = activeTab === "vietnamese" ? "-vi" : "";
    const blob = new Blob([activeContent], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `research${suffix}-${topic.slice(0, 30).replace(/\s+/g, "-")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleTranslate = async () => {
    setTranslating(true);
    setTranslateError("");
    try {
      const res = await fetch("/api/v1/research/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report, topic }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Dịch thất bại");
      }
      const data = await res.json();
      setViReport(data.translated_report);
    } catch (e: unknown) {
      setTranslateError(e instanceof Error ? e.message : "Có lỗi xảy ra khi dịch");
    } finally {
      setTranslating(false);
    }
  };

  const wordCount = activeContent.split(/\s+/).filter(Boolean).length;
  const citationCount = (report.match(/\[[a-f0-9]{6,8}\]/g) || []).length;

  const TABS: { id: Tab; label: string }[] = [
    { id: "report", label: "📄 Báo cáo (EN)" },
    { id: "vietnamese", label: "🇻🇳 Bản tiếng Việt" },
    { id: "sources", label: `🔍 Nguồn (${Object.keys(allSources).length})` },
  ];

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden animate-fade-in">
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 p-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="flex bg-slate-100 dark:bg-slate-800 rounded-lg p-1 gap-1">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                  activeTab === tab.id
                    ? "bg-white dark:bg-slate-700 shadow-sm text-slate-900 dark:text-white"
                    : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Stats + actions */}
        <div className="flex items-center gap-3">
          {activeTab !== "sources" && (
            <div className="text-xs text-slate-400 space-x-2 hidden sm:block">
              <span>{wordCount.toLocaleString()} từ</span>
              <span>·</span>
              <span>{citationCount} trích dẫn</span>
              <span>·</span>
              <span>{bibliography.length} nguồn</span>
            </div>
          )}
          {activeTab !== "sources" && activeContent && (
            <>
              <button
                onClick={handleCopy}
                className="text-xs px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition-colors"
              >
                {copied ? "✓ Đã sao chép!" : "Sao chép MD"}
              </button>
              <button
                onClick={handleDownload}
                className="text-xs px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors"
              >
                ↓ Tải xuống
              </button>
            </>
          )}
        </div>
      </div>

      {/* Report tab (English) */}
      {activeTab === "report" && (
        <div className="p-6 overflow-auto max-h-[70vh]">
          <div className="report-content max-w-4xl mx-auto">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Vietnamese translation tab */}
      {activeTab === "vietnamese" && (
        <div className="p-6 overflow-auto max-h-[70vh]">
          {!viReport && !translating && (
            <div className="flex flex-col items-center justify-center py-16 gap-5">
              <div className="text-5xl">🇻🇳</div>
              <div className="text-center max-w-md">
                <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100 mb-2">
                  Dịch báo cáo sang tiếng Việt
                </h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
                  Hệ thống sẽ dịch toàn bộ nội dung báo cáo sang tiếng Việt học thuật,
                  giữ nguyên cấu trúc Markdown, bảng biểu và trích dẫn nguồn.
                </p>
                {translateError && (
                  <div className="mb-4 p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
                    ⚠️ {translateError}
                  </div>
                )}
                <button
                  onClick={handleTranslate}
                  className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-colors"
                >
                  🌐 Bắt đầu dịch
                </button>
              </div>
            </div>
          )}

          {translating && (
            <div className="flex flex-col items-center justify-center py-16 gap-4">
              <div className="w-10 h-10 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
              <div className="text-center">
                <p className="font-medium text-slate-700 dark:text-slate-200">Đang dịch báo cáo...</p>
                <p className="text-sm text-slate-400 mt-1">Quá trình này có thể mất 30–60 giây tuỳ độ dài báo cáo</p>
              </div>
            </div>
          )}

          {viReport && !translating && (
            <>
              <div className="mb-4 flex items-center justify-between">
                <span className="inline-flex items-center gap-2 text-xs text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950 border border-emerald-200 dark:border-emerald-800 rounded-full px-3 py-1">
                  ✓ Đã dịch sang tiếng Việt
                </span>
                <button
                  onClick={handleTranslate}
                  className="text-xs px-3 py-1.5 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 underline"
                >
                  Dịch lại
                </button>
              </div>
              <div className="report-content max-w-4xl mx-auto">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{viReport}</ReactMarkdown>
              </div>
            </>
          )}
        </div>
      )}

      {/* Sources tab */}
      {activeTab === "sources" && (
        <div className="p-5 overflow-auto max-h-[70vh]">
          {/* Summary stats */}
          <div className="grid grid-cols-3 gap-3 mb-5">
            <div className="bg-emerald-50 dark:bg-emerald-950 border border-emerald-200 dark:border-emerald-800 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-emerald-700 dark:text-emerald-300">{credibleSources.length}</div>
              <div className="text-xs text-emerald-600 dark:text-emerald-400 mt-0.5">Nguồn tin cậy</div>
            </div>
            <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-red-700 dark:text-red-300">{discardedSources.length}</div>
              <div className="text-xs text-red-600 dark:text-red-400 mt-0.5">Đã loại bỏ</div>
            </div>
            <div className="bg-indigo-50 dark:bg-indigo-950 border border-indigo-200 dark:border-indigo-800 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-indigo-700 dark:text-indigo-300">
                {credibleSources.length > 0
                  ? (credibleSources.reduce((acc, s) => acc + s.total_score, 0) / credibleSources.length).toFixed(1)
                  : "—"}
              </div>
              <div className="text-xs text-indigo-600 dark:text-indigo-400 mt-0.5">Điểm TB</div>
            </div>
          </div>

          {/* Credible sources */}
          {credibleSources.length > 0 && (
            <>
              <h3 className="font-semibold text-sm text-slate-700 dark:text-slate-300 mb-3">
                ✓ Nguồn tin cậy (dùng trong báo cáo)
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
                ✗ Nguồn đã loại ({discardedSources.length}) — nhấn để xem
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
