"use client";

import { useState, useRef, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Phase = "idle" | "streaming" | "done" | "error";

const PHASE_LABELS: Record<string, string> = {
  CLARIFY: "Clarifying...",
  AUTO_REPLY: "Processing...",
  SCOPE: "Scoping MVP...",
  RISK: "Identifying risk...",
  BRIEF: "Writing brief...",
};

export default function Home() {
  const [idea, setIdea] = useState("");
  const [output, setOutput] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [currentPhaseLabel, setCurrentPhaseLabel] = useState("");
  const [savedPath, setSavedPath] = useState("");
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!idea.trim() || phase === "streaming") return;

    setOutput("");
    setSavedPath("");
    setPhase("streaming");
    setCurrentPhaseLabel("Starting...");

    try {
      const res = await fetch(`${API_BASE}/brief/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idea: idea.trim() }),
      });

      if (!res.ok) throw new Error(`API error: ${res.status}`);

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6);

          if (data === "[DONE]") {
            setPhase("done");
            setCurrentPhaseLabel("");
          } else if (data.startsWith("[PHASE:")) {
            const name = data.slice(7, -1);
            setCurrentPhaseLabel(PHASE_LABELS[name] ?? name);
          } else if (data.startsWith("[SAVED:")) {
            setSavedPath(data.slice(7, -1));
          } else if (data.startsWith("ERROR:")) {
            setOutput((prev) => prev + `\n\n⚠️ ${data}`);
            setPhase("error");
          } else {
            setOutput((prev) => prev + data.replace(/\\n/g, "\n"));
          }
        }
      }
    } catch (err) {
      setOutput((prev) => prev + `\n\n⚠️ ${String(err)}`);
      setPhase("error");
    }
  }

  function handleSave() {
    if (!output) return;
    const blob = new Blob([output], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `brief-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col items-center px-4 py-12">
      <div className="w-full max-w-3xl flex flex-col gap-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Prototype Pilot</h1>
          <p className="text-zinc-400 text-sm mt-1">
            Your AI co-founder. Drop an idea, get a build brief.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <textarea
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            placeholder="Describe your idea in plain English. E.g. 'An app that helps freelancers track client payments and send reminders automatically.'"
            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg p-4 text-sm text-zinc-100 placeholder-zinc-500 resize-none focus:outline-none focus:border-zinc-400 transition-colors"
            rows={4}
            disabled={phase === "streaming"}
          />
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={!idea.trim() || phase === "streaming"}
              className="px-5 py-2 bg-zinc-100 text-zinc-900 text-sm font-semibold rounded-lg disabled:opacity-40 disabled:cursor-not-allowed hover:bg-white transition-colors"
            >
              {phase === "streaming" ? "Running..." : "Generate Brief"}
            </button>
            {phase === "streaming" && (
              <span className="text-zinc-400 text-sm animate-pulse">
                {currentPhaseLabel}
              </span>
            )}
          </div>
        </form>

        {(output || phase === "streaming") && (
          <div className="flex flex-col gap-3">
            <div
              ref={outputRef}
              className="bg-zinc-900 border border-zinc-800 rounded-lg p-5 text-sm text-zinc-200 font-mono leading-relaxed whitespace-pre-wrap overflow-y-auto max-h-[600px]"
            >
              {output || (
                <span className="text-zinc-500 animate-pulse">Thinking...</span>
              )}
            </div>

            {phase === "done" && (
              <div className="flex items-center justify-between">
                <div className="flex gap-2">
                  <button
                    onClick={handleSave}
                    className="px-4 py-2 bg-zinc-800 text-zinc-100 text-sm rounded-lg hover:bg-zinc-700 transition-colors border border-zinc-700"
                  >
                    Download .md
                  </button>
                  <button
                    onClick={() => { setOutput(""); setSavedPath(""); setPhase("idle"); }}
                    className="px-4 py-2 bg-zinc-900 text-zinc-400 text-sm rounded-lg hover:text-zinc-200 transition-colors border border-zinc-700"
                  >
                    New idea
                  </button>
                </div>
                {savedPath && (
                  <span className="text-zinc-500 text-xs truncate max-w-xs">
                    Saved: {savedPath.split(/[/\\]/).pop()}
                  </span>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
