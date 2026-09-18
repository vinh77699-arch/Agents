"use client";
import { useState } from "react";
import { apiLogin, apiRegister, saveAuth, type AuthUser } from "@/lib/auth";

interface Props {
  onSuccess: (user: AuthUser) => void;
  onClose: () => void;
}

export function AuthModal({ onSuccess, onClose }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const fn = mode === "login" ? apiLogin : apiRegister;
      const { access_token, user } = await fn(email, password);
      saveAuth(access_token, user as AuthUser);
      onSuccess(user as AuthUser);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Có lỗi xảy ra");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-md p-8 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xl"
        >
          ✕
        </button>

        <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">
          {mode === "login" ? "Đăng nhập" : "Tạo tài khoản"}
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
          {mode === "login"
            ? "Đăng nhập để lưu lịch sử nghiên cứu"
            : "Đăng ký để nhận 5 báo cáo/ngày"}
        </p>

        <form onSubmit={submit} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-4 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="ten@email.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Mật khẩu</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full px-4 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="Tối thiểu 6 ký tự"
            />
          </div>

          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
              ⚠️ {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
          >
            {loading && <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
            {mode === "login" ? "Đăng nhập" : "Tạo tài khoản"}
          </button>
        </form>

        <p className="text-center text-sm text-slate-500 dark:text-slate-400 mt-5">
          {mode === "login" ? "Chưa có tài khoản? " : "Đã có tài khoản? "}
          <button
            onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
            className="text-indigo-600 dark:text-indigo-400 font-medium hover:underline"
          >
            {mode === "login" ? "Đăng ký ngay" : "Đăng nhập"}
          </button>
        </p>
      </div>
    </div>
  );
}
