"use client";
import { useState, useCallback, useEffect } from "react";
import { ResearchForm } from "@/components/ResearchForm";
import { PipelineProgress } from "@/components/PipelineProgress";
import { ReportViewer } from "@/components/ReportViewer";
import { AuthModal } from "@/components/AuthModal";
import { SessionHistory } from "@/components/SessionHistory";
import { DocumentUpload } from "@/components/DocumentUpload";
import { streamResearch } from "@/lib/api";
import { getUser, clearAuth, authHeaders, type AuthUser } from "@/lib/auth";
import type { AgentState, PipelineEvent, SourceInfo } from "@/types";

const INITIAL_AGENTS: AgentState[] = [
  { name: "planner", label: "Planner Agent", status: "pending", message: "Waiting...", icon: "🗺️" },
  { name: "searcher", label: "Search & Scraper Agent", status: "pending", message: "Waiting...", icon: "🔍" },
  { name: "credibility", label: "Credibility Evaluator", status: "pending", message: "Waiting...", icon: "⭐" },
  { name: "synthesizer", label: "Synthesis Agent (RAG)", status: "pending", message: "Waiting...", icon: "🧬" },
  { name: "report_writer", label: "Report Writer Agent", status: "pending", message: "Waiting...", icon: "📝" },
];

export default function Home() {
  const [isLoading, setIsLoading] = useState(false);
  const [agents, setAgents] = useState<AgentState[]>(INITIAL_AGENTS);
  const [report, setReport] = useState<string | null>(null);
  const [bibliography, setBibliography] = useState<string[]>([]);
  const [allSources, setAllSources] = useState<Record<string, SourceInfo>>({});
  const [currentTopic, setCurrentTopic] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [searchCallsUsed, setSearchCallsUsed] = useState(0);
  const [retryCount, setRetryCount] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);

  // Auth & modals
  const [user, setUser] = useState<AuthUser | null>(null);
  const [showAuth, setShowAuth] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showUpload, setShowUpload] = useState(false);

  useEffect(() => {
    setUser(getUser());
  }, []);

  const updateAgent = useCallback((name: string, updates: Partial<AgentState>) => {
    setAgents((prev) => prev.map((a) => (a.name === name ? { ...a, ...updates } : a)));
  }, []);

  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const res = await fetch(`/api/v1/research/${sessionId}/report`, { headers: authHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      setCurrentTopic(data.topic);
      setReport(data.report);
      setBibliography(data.bibliography || []);
      setAllSources(data.all_sources || {});
      setAgents(INITIAL_AGENTS.map((a) => ({ ...a, status: "completed", message: "Done" })));
    } catch {}
  }, []);

  const handleResearch = useCallback(async (topic: string) => {
    setIsLoading(true);
    setCurrentTopic(topic);
    setReport(null);
    setBibliography([]);
    setAllSources({});
    setError(null);
    setLogs([]);
    setSearchCallsUsed(0);
    setRetryCount(0);
    setAgents(INITIAL_AGENTS);

    try {
      for await (const event of streamResearch(topic)) {
        handleEvent(event);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setLogs((prev) => [...prev, `ERROR: ${msg}`]);
    } finally {
      setIsLoading(false);
    }

    function handleEvent(event: PipelineEvent) {
      const { type, agent, message, data } = event;
      const ts = new Date().toLocaleTimeString();

      if (type === "agent_start" && agent) {
        updateAgent(agent, { status: "running", message: message || "Running..." });
        setLogs((p) => [...p, `[${ts}] ${agent}: started`]);
      }
      if (type === "agent_complete" && agent) {
        updateAgent(agent, { status: "completed", message: message || "Done", data: data as Record<string, unknown> });
        setLogs((p) => [...p, `[${ts}] ${agent}: ${message || "completed"}`]);
        if (data?.calls_used) setSearchCallsUsed((prev) => prev + Number(data.calls_used));
      }
      if (type === "progress") {
        if (agent) updateAgent(agent, { message: message || "" });
        if (data?.retry_count) setRetryCount(Number(data.retry_count));
        setLogs((p) => [...p, `[${ts}] ${message || ""}`]);
      }
      if (type === "complete") {
        setReport(event.report || "");
        setBibliography(event.bibliography || []);
        setAllSources((event.all_sources as Record<string, SourceInfo>) || {});
        setLogs((p) => [...p, `[${ts}] Nghiên cứu hoàn thành!`]);
        // refresh user quota
        if (user) {
          fetch("/api/v1/auth/me", { headers: authHeaders() })
            .then((r) => r.json())
            .then((u) => setUser((prev) => prev ? { ...prev, reports_today: u.reports_today } : prev))
            .catch(() => {});
        }
      }
      if (type === "error") {
        setError(event.message || "Unknown error");
        setLogs((p) => [...p, `[${ts}] ERROR: ${event.message}`]);
      }
    }
  }, [updateAgent, user]);

  const hasStarted = agents.some((a) => a.status !== "pending");
  const isComplete = !!report;

  return (
    <>
      {/* Auth / History / Upload modals */}
      {showAuth && (
        <AuthModal
          onSuccess={(u) => { setUser(u); setShowAuth(false); }}
          onClose={() => setShowAuth(false)}
        />
      )}
      {showHistory && (
        <SessionHistory
          onLoadSession={loadSession}
          onClose={() => setShowHistory(false)}
        />
      )}
      {showUpload && <DocumentUpload onClose={() => setShowUpload(false)} />}

      {/* Top toolbar */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="flex items-center gap-2">
          {user && (
            <>
              <button
                onClick={() => setShowHistory(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition-colors text-slate-700 dark:text-slate-300"
              >
                📋 Lịch sử
              </button>
              <button
                onClick={() => setShowUpload(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition-colors text-slate-700 dark:text-slate-300"
              >
                📎 Tài liệu
              </button>
            </>
          )}
        </div>

        <div className="flex items-center gap-3">
          {user ? (
            <div className="flex items-center gap-3">
              <div className="text-xs text-slate-500 dark:text-slate-400 text-right hidden sm:block">
                <div className="font-medium text-slate-700 dark:text-slate-200">{user.email}</div>
                <div>
                  {user.role === "admin" ? "👑 Admin" : `${user.reports_today ?? 0}/${user.daily_quota} báo cáo hôm nay`}
                </div>
              </div>
              <button
                onClick={() => { clearAuth(); setUser(null); }}
                className="text-xs px-3 py-1.5 border border-slate-300 dark:border-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors text-slate-600 dark:text-slate-300"
              >
                Đăng xuất
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowAuth(true)}
              className="text-sm px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-colors"
            >
              Đăng nhập
            </button>
          )}
        </div>
      </div>

      <div className="space-y-6">
        {/* Hero */}
        {!hasStarted && !isLoading && (
          <div className="text-center py-4">
            <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-2">
              AI Research & Report Generator
            </h1>
            <p className="text-slate-500 dark:text-slate-400 max-w-2xl mx-auto text-sm sm:text-base">
              Pipeline đa tác nhân tự động tìm kiếm, đánh giá độ tin cậy nguồn và tạo báo cáo nghiên cứu
              học thuật có trích dẫn đầy đủ.
            </p>
          </div>
        )}

        <div className={`grid gap-6 ${hasStarted ? "lg:grid-cols-5" : ""}`}>
          {/* Left */}
          <div className={`space-y-4 ${hasStarted ? "lg:col-span-2" : ""}`}>
            <ResearchForm onSubmit={handleResearch} isLoading={isLoading} />

            {hasStarted && (
              <PipelineProgress
                agents={agents}
                isRunning={isLoading}
                searchCallsUsed={searchCallsUsed}
                retryCount={retryCount}
              />
            )}

            {error && (
              <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 text-sm text-red-700 dark:text-red-300">
                <strong>Lỗi:</strong> {error}
                {error.includes("429") || error.includes("hạn mức") ? (
                  <p className="text-xs mt-1 text-red-500">Bạn đã đạt giới hạn báo cáo trong ngày.</p>
                ) : (
                  <p className="text-xs mt-1 text-red-500">Kiểm tra backend đang chạy và API key đã được cấu hình.</p>
                )}
              </div>
            )}

            {logs.length > 0 && (
              <details className="text-xs">
                <summary className="cursor-pointer text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 py-1">
                  📋 Nhật ký hoạt động ({logs.length} dòng)
                </summary>
                <div className="mt-2 bg-slate-900 text-green-400 rounded-lg p-3 max-h-48 overflow-y-auto font-mono space-y-0.5">
                  {logs.map((log, i) => <div key={i} className="opacity-80">{log}</div>)}
                </div>
              </details>
            )}
          </div>

          {/* Right */}
          {hasStarted && (
            <div className="lg:col-span-3">
              {isLoading && !report && (
                <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-8 text-center shadow-sm">
                  <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4" />
                  <p className="text-slate-500 dark:text-slate-400">Đang tạo báo cáo nghiên cứu...</p>
                  <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Thường mất 2–5 phút</p>
                </div>
              )}
              {report && (
                <ReportViewer
                  report={report}
                  bibliography={bibliography}
                  allSources={allSources}
                  topic={currentTopic}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
