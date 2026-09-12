"use client";
import { useState, useCallback } from "react";
import { ResearchForm } from "@/components/ResearchForm";
import { PipelineProgress } from "@/components/PipelineProgress";
import { ReportViewer } from "@/components/ReportViewer";
import { streamResearch } from "@/lib/api";
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

  const updateAgent = useCallback((name: string, updates: Partial<AgentState>) => {
    setAgents((prev) =>
      prev.map((a) => (a.name === name ? { ...a, ...updates } : a))
    );
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
        updateAgent(agent, {
          status: "completed",
          message: message || "Done",
          data: data as Record<string, unknown>,
        });
        setLogs((p) => [...p, `[${ts}] ${agent}: ${message || "completed"}`]);

        if (data?.calls_used) setSearchCallsUsed((prev) => prev + Number(data.calls_used));
      }

      if (type === "progress") {
        if (agent) {
          updateAgent(agent, { message: message || "" });
        }
        if (data?.retry_count) setRetryCount(Number(data.retry_count));
        setLogs((p) => [...p, `[${ts}] ${message || ""}`]);
      }

      if (type === "complete") {
        setReport(event.report || "");
        setBibliography(event.bibliography || []);
        setAllSources((event.all_sources as Record<string, SourceInfo>) || {});
        setLogs((p) => [...p, `[${ts}] Research complete!`]);
      }

      if (type === "error") {
        setError(event.message || "Unknown error");
        setLogs((p) => [...p, `[${ts}] ERROR: ${event.message}`]);
      }
    }
  }, [updateAgent]);

  const hasStarted = agents.some((a) => a.status !== "pending");
  const isComplete = !!report;

  return (
    <div className="space-y-6">
      {/* Hero */}
      {!hasStarted && !isLoading && (
        <div className="text-center py-4">
          <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-2">
            AI Research & Report Generator
          </h1>
          <p className="text-slate-500 dark:text-slate-400 max-w-2xl mx-auto text-sm sm:text-base">
            Multi-agent pipeline that searches the web, evaluates source credibility, and generates
            structured research reports with full citations.
          </p>
        </div>
      )}

      <div className={`grid gap-6 ${hasStarted ? "lg:grid-cols-5" : ""}`}>
        {/* Left: form + progress */}
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

          {/* Error */}
          {error && (
            <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4 text-sm text-red-700 dark:text-red-300">
              <strong>Error:</strong> {error}
              <p className="text-xs mt-1 text-red-500">
                Make sure the backend is running and API keys are configured.
              </p>
            </div>
          )}

          {/* Live log (collapsed by default) */}
          {logs.length > 0 && (
            <details className="text-xs">
              <summary className="cursor-pointer text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 py-1">
                📋 Activity Log ({logs.length} entries)
              </summary>
              <div className="mt-2 bg-slate-900 text-green-400 rounded-lg p-3 max-h-48 overflow-y-auto font-mono space-y-0.5">
                {logs.map((log, i) => (
                  <div key={i} className="opacity-80">{log}</div>
                ))}
              </div>
            </details>
          )}
        </div>

        {/* Right: report */}
        {hasStarted && (
          <div className="lg:col-span-3">
            {isLoading && !report && (
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-8 text-center shadow-sm">
                <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4" />
                <p className="text-slate-500 dark:text-slate-400">
                  Generating your research report...
                </p>
                <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                  This typically takes 2-5 minutes
                </p>
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
  );
}
