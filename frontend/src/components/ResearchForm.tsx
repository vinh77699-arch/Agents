"use client";
import { useState } from "react";

const EXAMPLE_TOPICS = [
  "Impact of large language models on education in 2024-2025",
  "Mechanisms and treatments for long COVID",
  "Quantum computing applications in cryptography",
  "Climate change mitigation strategies effectiveness",
  "Microplastics effects on human health",
];

interface Props {
  onSubmit: (topic: string) => void;
  isLoading: boolean;
}

export function ResearchForm({ onSubmit, isLoading }: Props) {
  const [topic, setTopic] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (topic.trim().length >= 5 && !isLoading) {
      onSubmit(topic.trim());
    }
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
      <div className="mb-5">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-1">
          Start a Research Session
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Enter any research topic or question. The AI pipeline will automatically search, evaluate sources, and generate a structured report with citations.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="topic"
            className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5"
          >
            Research Topic / Question
          </label>
          <textarea
            id="topic"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. What are the long-term health effects of microplastic ingestion in humans?"
            rows={3}
            disabled={isLoading}
            className="w-full px-4 py-3 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none transition-colors disabled:opacity-50"
          />
          <div className="flex justify-between mt-1">
            <span className="text-xs text-slate-400">Minimum 5 characters</span>
            <span className={`text-xs ${topic.length > 450 ? "text-red-500" : "text-slate-400"}`}>
              {topic.length}/500
            </span>
          </div>
        </div>

        <button
          type="submit"
          disabled={topic.trim().length < 5 || isLoading}
          className="w-full py-3 px-6 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 disabled:from-slate-400 disabled:to-slate-400 text-white font-semibold rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-sm hover:shadow-md disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Researching...
            </>
          ) : (
            <>
              <span>🚀</span>
              Generate Research Report
            </>
          )}
        </button>
      </form>

      {/* Example topics */}
      <div className="mt-5">
        <p className="text-xs text-slate-400 dark:text-slate-500 mb-2 font-medium uppercase tracking-wide">
          Example topics
        </p>
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_TOPICS.map((t) => (
            <button
              key={t}
              onClick={() => setTopic(t)}
              disabled={isLoading}
              className="text-xs px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-indigo-50 dark:hover:bg-indigo-950 hover:text-indigo-700 dark:hover:text-indigo-300 text-slate-600 dark:text-slate-400 rounded-full border border-slate-200 dark:border-slate-700 transition-colors disabled:opacity-50 cursor-pointer"
            >
              {t.length > 50 ? t.slice(0, 50) + "…" : t}
            </button>
          ))}
        </div>
      </div>

      {/* Pipeline overview */}
      <div className="mt-5 p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
        <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
          Pipeline Overview
        </p>
        <div className="flex items-center gap-1 flex-wrap text-xs text-slate-600 dark:text-slate-400">
          {["🗺️ Plan", "→", "🔍 Search", "→", "⭐ Evaluate", "→", "🧬 Synthesize (RAG)", "→", "📝 Report"].map((step, i) => (
            <span
              key={i}
              className={step === "→" ? "text-slate-300 dark:text-slate-600" : "bg-white dark:bg-slate-700 px-2 py-0.5 rounded"}
            >
              {step}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
