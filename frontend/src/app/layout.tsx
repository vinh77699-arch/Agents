import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI Research Agent",
  description: "Multi-agent AI system for automated research report generation with credibility scoring",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className={inter.className}>
        <header className="border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center text-white text-sm font-bold">
              AI
            </div>
            <div>
              <h1 className="font-bold text-slate-900 dark:text-white text-sm sm:text-base">
                AI Research Agent
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400 hidden sm:block">
                Multi-agent research system with credibility scoring
              </p>
            </div>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
          {children}
        </main>
        <footer className="border-t border-slate-200 dark:border-slate-800 mt-12 py-6 text-center text-xs text-slate-400 dark:text-slate-600">
          AI Research Agent — Built with FastAPI, LangGraph, Next.js
        </footer>
      </body>
    </html>
  );
}
