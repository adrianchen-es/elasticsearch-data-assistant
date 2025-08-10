import React, { useCallback, useEffect, useRef, useState } from "react";

export default function ChatInterface() {
  const [messages, setMessages] = useState([
    // { role: "system", content: "You are a helpful assistant." } // if you use system prompts
  ]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);

  const appendAssistantChunk = useCallback((delta) => {
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (!last || last.role !== "assistant") {
        return [...prev, { role: "assistant", content: delta }];
      }
      // Append to the current assistant message
      const updated = [...prev];
      updated[updated.length - 1] = { ...last, content: (last.content || "") + delta };
      return updated;
    });
  }, []);

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isStreaming) return;

    setError(null);
    const newMessages = [...messages, { role: "user", content: input }];
    setMessages(newMessages);
    setInput("");
    setIsStreaming(true);

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: newMessages,
          stream: true,
        }),
      });

      if (!resp.ok && resp.headers.get("content-type")?.includes("application/json")) {
        const err = await resp.json();
        const friendly = err?.detail?.message || err?.detail?.error?.message || err?.detail || "Request failed.";
        setError(friendly);
        setIsStreaming(false);
        return;
      }

      // NDJSON streaming reader
      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      // Prepare an empty assistant message to start streaming into
      appendAssistantChunk("");

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let idx;
        while ((idx = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, idx).trim();
          buffer = buffer.slice(idx + 1);

          if (!line) continue;

          try {
            const event = JSON.parse(line);

            if (event.error) {
              const details = event.error.details;
              const msg =
                event.error.message ||
                "The assistant could not process your request.";
              const extra =
                details && details.prompt_tokens && details.context_window
                  ? ` (prompt tokens: ${details.prompt_tokens}/${details.context_window})`
                  : "";
              setError(msg + extra);
              continue;
            }

            if (event.type === "message" && event.delta) {
              appendAssistantChunk(event.delta);
            } else if (event.type === "final") {
              // Optionally, you can use event.usage to display token usage
              // console.log("Usage", event.usage);
            }
          } catch (e) {
            // Non-JSON line; ignore
          }
        }
      }
    } catch (e) {
      setError("Network error while contacting the assistant.");
    } finally {
      setIsStreaming(false);
    }
  }, [appendAssistantChunk, input, isStreaming, messages]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto p-4 space-y-3">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <div className="inline-block rounded px-3 py-2" style={{ background: m.role === "user" ? "#e5e7eb" : "#f3f4f6" }}>
              {m.content}
            </div>
          </div>
        ))}
        {error && (
          <div className="text-red-600 text-sm">
            {error}
          </div>
        )}
      </div>
      <div className="p-3 border-t flex gap-2">
        <input
          className="flex-1 border rounded px-3 py-2"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask something..."
          disabled={isStreaming}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage();
            }
          }}
        />
        <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={sendMessage} disabled={isStreaming}>
          {isStreaming ? "Streaming..." : "Send"}
        </button>
      </div>
    </div>
  );
}
