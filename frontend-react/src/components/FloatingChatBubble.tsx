import { useState } from "react"

import { api } from "../services/api"

type BubbleMessage = {
  role: "user" | "assistant"
  text: string
}

const QUICK_REPLIES = [
  { label: "Finance", key: "finance", prompt: "Help me compare financing options for this vehicle." },
  { label: "Trade-In", key: "trade-in", prompt: "I want a trade-in estimate and next steps." },
  { label: "Test Drive", key: "test-drive", prompt: "Help me schedule a test drive this week." },
  { label: "Compare", key: "compare", prompt: "Compare top options for value and reliability." },
]

type FloatingChatBubbleProps = {
  onRequestOpenFullChat?: (prompt: string) => void
}

export default function FloatingChatBubble({ onRequestOpenFullChat }: FloatingChatBubbleProps) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<BubbleMessage[]>([
    { role: "assistant", text: "Need help fast? Ask me about financing, trade-in, test drive, or comparisons." },
  ])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)

  const send = async (text: string, quickReply?: string) => {
    const question = text.trim()
    if (!question || loading) return

    setMessages((prev) => [...prev, { role: "user", text: question }])
    setInput("")
    setLoading(true)
    try {
      const answer = await api.ask(question, quickReply)
      setMessages((prev) => [...prev, { role: "assistant", text: answer }])
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", text: "I hit a connection issue. Please try again." }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed bottom-4 right-4 z-40">
      {open && (
        <div className="mb-3 w-[calc(100vw-2rem)] max-w-sm rounded-2xl border border-imperial-border dark:border-imperial-border-dark bg-imperial-surface dark:bg-imperial-surface-dark p-3 shadow-2xl">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-bold text-imperial-primary dark:text-imperial-primary-light">Imperial Assistant</p>
            <button type="button" onClick={() => setOpen(false)} className="text-xs font-semibold text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Close</button>
          </div>

          <div className="mb-3 flex max-h-64 flex-col gap-2 overflow-y-auto pr-1">
            {messages.map((m, index) => (
              <div key={`${m.role}-${index}`} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] rounded-xl px-3 py-2 text-xs ${m.role === "user" ? "bg-imperial-primary text-white" : "bg-imperial-bg-light dark:bg-imperial-bg-dark text-imperial-text dark:text-imperial-text-dark"}`}>
                  {m.text}
                </div>
              </div>
            ))}
            {loading && <div className="text-xs text-imperial-text-secondary dark:text-imperial-text-secondary-dark animate-pulse">Thinking...</div>}
          </div>

          <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Quick replies">
            {QUICK_REPLIES.map((chip) => (
              <button
                key={chip.key}
                type="button"
                onClick={() => send(chip.prompt, chip.key)}
                className="rounded-full border border-imperial-border dark:border-imperial-border-dark px-2.5 py-1 text-[11px] font-semibold text-imperial-primary dark:text-imperial-primary-light hover:bg-imperial-bg-light dark:hover:bg-imperial-bg-dark focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2"
              >
                {chip.label}
              </button>
            ))}
          </div>

          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") send(input)
              }}
              aria-label="Message Imperial assistant"
              placeholder="Ask anything..."
              className="w-full rounded-lg border border-imperial-border dark:border-imperial-border-dark px-3 py-2 text-xs bg-imperial-bg-light dark:bg-imperial-bg-dark text-imperial-text dark:text-imperial-text-dark"
            />
            <button type="button" onClick={() => send(input)} className="rounded-lg bg-imperial-primary px-3 py-2 text-xs font-semibold text-white hover:bg-imperial-primary-light focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2">
              Send
            </button>
          </div>

          <button
            type="button"
            onClick={() => onRequestOpenFullChat?.(input || "Help me compare current inventory options.")}
            className="mt-2 w-full rounded-lg border border-imperial-border dark:border-imperial-border-dark px-3 py-2 text-xs font-semibold text-imperial-primary dark:text-imperial-primary-light hover:bg-imperial-bg-light dark:hover:bg-imperial-bg-dark focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2"
          >
            Open Full Chat
          </button>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label={open ? "Close chat bubble" : "Open chat bubble"}
        className="h-14 w-14 rounded-full bg-imperial-primary text-sm font-extrabold text-white shadow-xl hover:bg-imperial-primary-light focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2"
      >
        AI
      </button>
    </div>
  )
}
