"use client";
import { useEffect, useState } from "react";
import { authHeaders } from "@/lib/auth";

interface SessionRow {
  id: string;
  topic: string;
  status: string;
  word_count: number;
  sources_count: number;
  created_at: string;
  completed_at: string;
}

interface Props {
  onLoadSession: (id: string) => void;
  onClose: () => void;
}

export function SessionHistory({ onLoadSession, onClose }: Props) {
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/research/sessions", { headers: authHeaders() })
      .then((r) => r.json())
      .then((d) => setSessions(d.sessions || []))
      .catch(() => setSessions([]))
      .finally(() => setLoading(false));
  }, []);

  const fmt = (iso: string) => {
    if (!iso) return "—";
    try { return new Date(iso).toLocaleString("vi-VN"); } catch { return iso; }
  };

  const STATUS_COLOR: Record<string, string> = {
    completed: "text-emerald-600 dark:text-emerald-400",
    running: "text-indigo-600 dark:text-indigo-400",
    error: "text-red-600 dark:text-red-400",
    pending: "text-slate-500",
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between p-6 border-b border-slate-200 dark:border-slate-700">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">📋 Lịch sử nghiên cứu</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xl">✕</button>
        </div>

        <div className="overflow-y-auto flex-1 p-4">
          {loading && (
            <div className="flex items-center justify-center py-12 gap-3 text-slate-500">
              <span className="w-5 h-5 border-2 border-slate-300 border-t-indigo-500 rounded-full animate-spin" />
              Đang tải...
            </div>
          )}

          {!loading && sessions.length === 0 && (
            <div className="text-center py-12 text-slate-500 dark:text-slate-400">
              <div className="text-4xl mb-3">📭</div>
              <p>Chưa có phiên nghiên cứu nào</p>
            </div>
          )}

          {!loading && sessions.map((s) => (
            <div
              key={s.id}
              className="group flex items-start justify-between gap-3 p-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-indigo-300 dark:hover:border-indigo-700 hover:bg-indigo-50/30 dark:hover:bg-indigo-950/30 transition-all mb-3"
            >
              <div className="flex-1 min-w-0">
                <p className="font-medium text-slate-800 dark:text-slate-100 truncate">{s.topic}</p>
                <div className="flex items-center gap-3 mt-1 text-xs text-slate-400">
                  <span className={`font-medium ${STATUS_COLOR[s.status] || "text-slate-500"}`}>
                    {s.status === "completed" ? "✓ Hoàn thành" : s.status === "running" ? "⟳ Đang chạy" : s.status === "error" ? "✗ Lỗi" : "⏳ Chờ"}
                  </span>
                  <span>·</span>
                  <span>{fmt(s.created_at)}</span>
                  {s.word_count > 0 && <><span>·</span><span>{s.word_count.toLocaleString()} từ</span></>}
                  {s.sources_count > 0 && <><span>·</span><span>{s.sources_count} nguồn</span></>}
                </div>
              </div>
              {s.status === "completed" && (
                <button
                  onClick={() => { onLoadSession(s.id); onClose(); }}
                  className="flex-shrink-0 px-3 py-1.5 text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  Mở báo cáo
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
