"use client";
import { useRef, useState } from "react";
import { authHeaders } from "@/lib/auth";

interface UploadedDoc {
  document_id: string;
  filename: string;
  file_size: number;
  text_length: number;
  created_at: string;
}

interface Props {
  onClose: () => void;
}

export function DocumentUpload({ onClose }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [docs, setDocs] = useState<UploadedDoc[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadDocs = async () => {
    try {
      const res = await fetch("/api/v1/documents", { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setDocs(data.documents || []);
      }
    } catch {}
  };

  useState(() => { loadDocs(); });

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError("");
    setSuccess("");
    setUploading(true);

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch("/api/v1/documents/upload", {
        method: "POST",
        headers: authHeaders(),
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Upload thất bại");
      }
      const data = await res.json();
      setSuccess(`✓ Đã lập chỉ mục "${file.name}" (${data.text_length.toLocaleString()} ký tự)`);
      await loadDocs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Có lỗi xảy ra");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleDelete = async (docId: string, filename: string) => {
    if (!confirm(`Xoá tài liệu "${filename}"?`)) return;
    await fetch(`/api/v1/documents/${docId}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    await loadDocs();
  };

  const fmt = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-xl flex flex-col overflow-hidden">
        <div className="flex items-center justify-between p-6 border-b border-slate-200 dark:border-slate-700">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">📎 Thư viện tài liệu</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xl">✕</button>
        </div>

        <div className="p-6 space-y-5">
          {/* Upload zone */}
          <div
            onClick={() => fileRef.current?.click()}
            className="border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-xl p-8 text-center cursor-pointer hover:border-indigo-400 dark:hover:border-indigo-500 hover:bg-indigo-50/30 dark:hover:bg-indigo-950/20 transition-all"
          >
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.txt,.md"
              className="hidden"
              onChange={handleUpload}
            />
            {uploading ? (
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-3 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
                <p className="text-slate-600 dark:text-slate-400">Đang lập chỉ mục...</p>
              </div>
            ) : (
              <>
                <div className="text-4xl mb-3">📄</div>
                <p className="font-medium text-slate-700 dark:text-slate-200">Nhấn để tải file lên</p>
                <p className="text-sm text-slate-400 mt-1">PDF, TXT, MD — tối đa 10MB</p>
              </>
            )}
          </div>

          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
              ⚠️ {error}
            </div>
          )}
          {success && (
            <div className="p-3 bg-emerald-50 dark:bg-emerald-950 border border-emerald-200 dark:border-emerald-800 rounded-lg text-sm text-emerald-700 dark:text-emerald-300">
              {success}
            </div>
          )}

          {/* Uploaded docs list */}
          {docs.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3">
                Tài liệu đã lập chỉ mục ({docs.length})
              </h3>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {docs.map((d) => (
                  <div key={d.document_id} className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">{d.filename}</p>
                      <p className="text-xs text-slate-400">{fmt(d.file_size)}</p>
                    </div>
                    <button
                      onClick={() => handleDelete(d.document_id, d.filename)}
                      className="ml-3 text-xs text-red-500 hover:text-red-700 flex-shrink-0"
                    >
                      Xoá
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
