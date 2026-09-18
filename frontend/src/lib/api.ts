import type { PipelineEvent } from "@/types";
import { authHeaders } from "@/lib/auth";

const API_BASE =
  typeof window !== "undefined" && process.env.NEXT_PUBLIC_API_URL
    ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1`
    : "/api/v1";

export async function* streamResearch(topic: string): AsyncGenerator<PipelineEvent> {
  const response = await fetch(`${API_BASE}/research/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ topic }),
  });

  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch {}
    throw new Error(detail);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6).trim();
        if (data) {
          try {
            yield JSON.parse(data) as PipelineEvent;
          } catch {
            // Skip malformed events
          }
        }
      }
    }
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
