"use client";

import { useEffect, useRef, useState } from "react";

type Message = {
  role: "user" | "assistant" | "error";
  content: string;
  toolCalls?: Array<{ tool: string; args: Record<string, unknown> }>;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ParsedSSEEvent = {
  eventType: string;
  data: string;
};

function parseSSEBlock(block: string): ParsedSSEEvent | null {
  const lines = block.split("\n");
  let eventType = "";
  const dataLines: string[] = [];

  for (const rawLine of lines) {
    const line = rawLine.replace(/\r$/, "");
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (dataLines.length === 0) return null;
  return { eventType, data: dataLines.join("\n") };
}

function splitSSEBuffer(buffer: string): { events: ParsedSSEEvent[]; remainder: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const blocks = normalized.split("\n\n");
  const remainder = blocks.pop() || "";
  const events: ParsedSSEEvent[] = [];

  for (const block of blocks) {
    const parsed = parseSSEBlock(block);
    if (parsed) events.push(parsed);
  }

  return { events, remainder };
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [prompts, setPrompts] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fallback = [
      "What were Logins (LD) in March 2025?",
      "Show Sanction Amount (All) by branch for Q2 2025",
      "How many Sanctions (All) in Q1 2025?",
      "What was Loan Amount (LD) in March 2025?",
      "How many First Disbursed (All) in July 2025?",
      "First Disbursed Amount (All) YTD through August 2025",
      "Loan Amount (LD) MTD for August 2025",
      "Show Logins (LD) by branch for March 2025",
      "Sanction Amount (All) by product for Q1 2025",
      "How many applications are credit declined in Q1 2025?",
      "How many applications are under CM review?",
      "Applications under CM review with more info required",
    ];
    fetch(`${API_URL}/api/suggested-prompts`)
      .then((r) => r.json())
      .then((data) => setPrompts(Array.isArray(data) && data.length ? data : fallback))
      .catch(() => setPrompts(fallback));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage(text: string) {
    if (!text.trim() || loading) return;

    const userMsg: Message = { role: "user", content: text.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    const history = messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({ role: m.role, content: m.content }));

    let assistantContent = "";
    const toolCalls: Array<{ tool: string; args: Record<string, unknown> }> = [];

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text.trim(), history }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`API error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const handleEvent = (eventType: string, data: string) => {
        let parsed: Record<string, unknown>;
        try {
          parsed = JSON.parse(data);
        } catch {
          return;
        }

        if (eventType === "text" || parsed.type === "text") {
          assistantContent = String(parsed.content || "");
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === "assistant") {
              next[next.length - 1] = { ...last, content: assistantContent, toolCalls };
            } else {
              next.push({ role: "assistant", content: assistantContent, toolCalls });
            }
            return next;
          });
        } else if (eventType === "tool" || parsed.type === "tool") {
          toolCalls.push({
            tool: String(parsed.tool),
            args: (parsed.args as Record<string, unknown>) || {},
          });
        } else if (eventType === "error" || parsed.type === "error") {
          setMessages((prev) => [
            ...prev,
            { role: "error", content: String(parsed.content || "Unknown error") },
          ]);
        }
      };

      const processBuffer = (chunk: string, flush = false) => {
        buffer += chunk;
        const { events, remainder } = splitSSEBuffer(buffer);
        buffer = flush ? "" : remainder;
        for (const event of events) {
          handleEvent(event.eventType, event.data);
        }
        if (flush && buffer.trim()) {
          const finalEvent = parseSSEBlock(buffer);
          if (finalEvent) handleEvent(finalEvent.eventType, finalEvent.data);
          buffer = "";
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        processBuffer(decoder.decode(value, { stream: true }));
      }

      processBuffer(decoder.decode(), true);

      if (assistantContent) {
        setMessages((prev) => {
          const filtered = prev.filter(
            (m, i) => !(i === prev.length - 1 && m.role === "assistant" && !m.content)
          );
          const last = filtered[filtered.length - 1];
          if (last?.role === "assistant") {
            filtered[filtered.length - 1] = {
              role: "assistant",
              content: assistantContent,
              toolCalls,
            };
            return filtered;
          }
          return [...filtered, { role: "assistant", content: assistantContent, toolCalls }];
        });
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "error",
          content: err instanceof Error ? err.message : "Failed to reach API",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app">
      <header className="header">
        <h1>Loan Analytics Chat</h1>
        <p>
          Agentic self-service analytics — governed DAX metrics, PostgreSQL, Gemini
        </p>
      </header>

      <div className="prompts">
        {prompts.map((p) => (
          <button
            key={p}
            className="prompt-btn"
            onClick={() => sendMessage(p)}
            disabled={loading}
          >
            {p}
          </button>
        ))}
      </div>

      <div className="messages">
        {messages.length === 0 && (
          <div className="message assistant">
            Ask about logins, sanctions, disbursements, or credit pipeline status.
            I use governed metrics aligned with your Power BI DAX first.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            {m.content}
            {m.toolCalls && m.toolCalls.length > 0 && (
              <details className="tool-panel">
                <summary>How this was calculated ({m.toolCalls.length} tool calls)</summary>
                <pre>{JSON.stringify(m.toolCalls, null, 2)}</pre>
              </details>
            )}
          </div>
        ))}
        {loading && <div className="typing">Analyzing…</div>}
        <div ref={bottomRef} />
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          sendMessage(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about loan analytics…"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </main>
  );
}
