import type { PipelineEvent } from "@/types";

// Always use the Next.js rewrite proxy (/api/v1 → backend).
// For local dev without Docker, set NEXT_PUBLIC_API_URL=http://localhost:8000
// and start the backend separately.
const API_BASE =
  typeof window !== "undefined" && process.env.NEXT_PUBLIC_API_URL
    ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1`
    : "/api/v1";

export async function* streamResearch(topic: string): AsyncGenerator<PipelineEvent> {
  const response = await fetch(`${API_BASE}/research/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
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
