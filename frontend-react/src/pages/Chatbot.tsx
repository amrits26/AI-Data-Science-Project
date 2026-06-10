import { useState, useRef, useEffect, useMemo } from "react";
import ReactMarkdown from "react-markdown";

import PaperworkPanel from "../components/PaperworkPanel";
import VisualizationsPanel from "../components/visualizations/VisualizationsPanel";
import { Allotment } from "allotment";
import "allotment/dist/style.css";
import { api } from "../services/api";
import type { AskResponseDetailed, VehicleMetadata } from "../types";

type Message = {
  role: "user" | "ai";
  content: string;
  source?: string;
  questionType?: string;
  metadata?: AskResponseDetailed["metadata"];
  id?: string;
  feedback?: "up" | "down" | null;
  error?: boolean;
};

const CHAT_MEMORY_KEY = "imperial-chat-last-qa";
const CHAT_CONTEXT_KEY = "imperial-chat-context";

type ChatbotProps = {
  prefilledPrompt?: string;
};


export default function Chatbot({ prefilledPrompt = "" }: ChatbotProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [chatContext, setChatContext] = useState<Record<string, any>>({});
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showRetry, setShowRetry] = useState(false);
  const [lastUserMessage, setLastUserMessage] = useState<string>("");
  const [showEscalation, setShowEscalation] = useState(false);
  const [leadName, setLeadName] = useState("");
  const [leadPhone, setLeadPhone] = useState("");
  const [leadEmail, setLeadEmail] = useState("");
  const [leadStatus, setLeadStatus] = useState("");
  const [submittingLead, setSubmittingLead] = useState(false);
  const [greeting, setGreeting] = useState<string | null>(null);
  const [interests, setInterests] = useState<string[]>([]);
  // --- Paperwork state ---
  const [dealSession, setDealSession] = useState<any>(null);
  const [pdfUrl, setPdfUrl] = useState<string | undefined>(undefined);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Feedback handler
  const handleFeedback = async (msgIdx: number, rating: "up" | "down") => {
    const msg = messages[msgIdx];
    if (!msg || msg.role !== "ai" || msg.feedback) return;
    const message_id = msg.id || `${msgIdx}-${Date.now()}`;
    const payload = {
      message_id,
      rating,
      user_comment: "",
    };
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setMessages((prev) => prev.map((m, i) => i === msgIdx ? { ...m, feedback: rating, id: message_id } : m));
    } catch (e) {
      // Optionally show error
    }
  };

  const scrollToBottom = () => {
    if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === "function") {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  const handleVoiceInput = () => {
    const speechCtor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!speechCtor) {
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: "Voice input is not supported on this browser.",
          source: "fallback",
          questionType: "general",
        },
      ]);
      return;
    }

    const recognition = new speechCtor();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event: any) => {
      const transcript = String(event?.results?.[0]?.[0]?.transcript || "").trim();
      if (transcript) {
        setInput(transcript);
      }
    };
    recognition.onerror = () => {
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: "Voice input is not supported on this browser.",
          source: "fallback",
          questionType: "general",
        },
      ]);
    };
    recognition.start();
  };

  const latestUserQuestion = useMemo(() => {
    for (let idx = messages.length - 1; idx >= 0; idx -= 1) {
      if (messages[idx].role === "user") {
        return messages[idx].content;
      }
    }
    return "";
  }, [messages]);

  const saveMessageMemory = (nextMessages: Message[]) => {
    const qaOnly = nextMessages.filter((msg) => msg.role === "user" || msg.role === "ai");
    const lastTen = qaOnly.slice(-10);
    window.localStorage.setItem(CHAT_MEMORY_KEY, JSON.stringify(lastTen));
  };

  const saveContextMemory = (nextContext: Record<string, any>) => {
    window.localStorage.setItem(CHAT_CONTEXT_KEY, JSON.stringify(nextContext || {}));
  };

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(CHAT_MEMORY_KEY);
      if (!raw) {
        return;
      }
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) {
        return;
      }
      const restored = parsed
        .filter((item) => item && (item.role === "user" || item.role === "ai") && typeof item.content === "string")
        .map((item) => ({
          role: item.role as "user" | "ai",
          content: item.content as string,
          source: typeof item.source === "string" ? item.source : undefined,
        }));
      if (restored.length > 0) {
        setMessages(restored.slice(-10));
      }
    } catch {
      window.localStorage.removeItem(CHAT_MEMORY_KEY);
    }

    try {
      const rawContext = window.localStorage.getItem(CHAT_CONTEXT_KEY);
      if (rawContext) {
        const parsedContext = JSON.parse(rawContext);
        if (parsedContext && typeof parsedContext === "object") {
          setChatContext(parsedContext);
        }
      }
    } catch {
      window.localStorage.removeItem(CHAT_CONTEXT_KEY);
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (prefilledPrompt.trim()) {
      setInput(prefilledPrompt.trim());
    }
  }, [prefilledPrompt]);

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMessage = input.trim();
    const userEntry: Message = { role: "user", content: userMessage };
    setInput("");
    setMessages((prev) => {
      const next: Message[] = [...prev, userEntry];
      saveMessageMemory(next);
      return next;
    });
    setLoading(true);

    // Streaming AI response
    let aiMsgIdx = -1;
    let buffer = "";
    try {
      setMessages((prev) => {
        const next: Message[] = [...prev, { role: "ai", content: "" }];
        aiMsgIdx = next.length - 1;
        return next;
      });
      await api.askStream(
        userMessage,
        chatContext,
        (chunk) => {
          buffer = chunk.content;
          setMessages((prev) => {
            const next = [...prev];
            if (next[aiMsgIdx] && next[aiMsgIdx].role === "ai") {
              next[aiMsgIdx] = { ...next[aiMsgIdx], content: buffer };
            }
            return next;
          });
        }
      );
      if (messages.length === 0 && buffer && /^welcome back[,! ]/i.test(buffer)) {
        setGreeting(buffer.split(". ")[0]);
        const found: string[] = [];
        if (/viewed:/i.test(buffer)) found.push("Vehicles viewed");
        if (/trade-in/i.test(buffer)) found.push("Trade-in interest");
        if (/financing/i.test(buffer)) found.push("Financing interest");
        if (/budget/i.test(buffer)) found.push("Budget discussed");
        setInterests(found);
      }
      setMessages((prev) => {
        saveMessageMemory(prev);
        return prev;
      });
      setLastUserMessage(userMessage);
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content: "Sorry, I couldn't reach the AI service. Please try again later.",
          source: "fallback",
          questionType: "general",
          error: true,
        },
      ]);
      setShowRetry(true);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = () => {
    setShowRetry(false);
    setInput(lastUserMessage);
    setTimeout(() => handleSend(), 100);
  };

  const submitEscalation = async () => {
    setLeadStatus("");
    setSubmittingLead(true);
    try {
      const response = await api.submitLead({
        name: leadName || "Chat User",
        phone: leadPhone || undefined,
        email: leadEmail || undefined,
        context: {
          channel: "chatbot",
          last_question: latestUserQuestion,
          chat_context: chatContext,
        },
      });
      if (response.status === "ok") {
        setLeadStatus("Thanks. A salesperson will follow up shortly.");
      } else {
        setLeadStatus(response.message || "Unable to save your request right now.");
      }
    } catch (error: any) {
      setLeadStatus(error?.message || "Unable to create escalation request right now.");
    } finally {
      setSubmittingLead(false);
    }
  };

  const renderComparison = (metadata?: AskResponseDetailed["metadata"]) => {
    const left = metadata?.comparison?.left;
    const right = metadata?.comparison?.right;
    if (!left || !right) {
      return null;
    }

    const price = (car: VehicleMetadata) => car.price ?? car.msrp ?? car.used_avg_price;
    const label = (car: VehicleMetadata) => `${car.year || ""} ${car.make || ""} ${car.model || ""} ${car.trim || ""}`.trim();

    const rows: Array<{ key: string; left: string; right: string }> = [
      { key: "Price", left: price(left) ? `$${Number(price(left)).toLocaleString()}` : "N/A", right: price(right) ? `$${Number(price(right)).toLocaleString()}` : "N/A" },
      { key: "Horsepower", left: left.horsepower ? String(left.horsepower) : "N/A", right: right.horsepower ? String(right.horsepower) : "N/A" },
      { key: "Torque", left: left.torque ? String(left.torque) : "N/A", right: right.torque ? String(right.torque) : "N/A" },
      { key: "MPG Hwy", left: left.mpg_highway ? String(left.mpg_highway) : "N/A", right: right.mpg_highway ? String(right.mpg_highway) : "N/A" },
      { key: "Towing", left: left.towing_capacity ? String(left.towing_capacity) : "N/A", right: right.towing_capacity ? String(right.towing_capacity) : "N/A" },
    ];

    return (
      <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="min-w-full text-xs">
          <thead className="bg-slate-50 text-slate-700">
            <tr>
              <th className="px-2 py-2 text-left">Metric</th>
              <th className="px-2 py-2 text-left">{label(left)}</th>
              <th className="px-2 py-2 text-left">{label(right)}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className="border-t border-slate-100">
                <td className="px-2 py-2 font-semibold text-slate-700">{row.key}</td>
                <td className="px-2 py-2 text-slate-600">{row.left}</td>
                <td className="px-2 py-2 text-slate-600">{row.right}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const handleEstimatePayment = (vehicle: VehicleMetadata) => {
    const title = `${vehicle.year || ""} ${vehicle.make || ""} ${vehicle.model || ""} ${vehicle.trim || ""}`.trim();
    setInput(`Estimate monthly payment for ${title}`.trim());
  };



  const sourceLabel = (source?: string) => {
    const normalized = String(source || "fallback").toLowerCase();
    if (normalized === "knowledge_base") return "Source: Knowledge Base";
    if (normalized === "inventory") return "Source: Live Inventory";
    if (normalized === "winning_script") return "Source: Winning Script";
    if (normalized === "routed_action") return "Source: Guided Action";
    return "Source: Fallback";
  };

  // --- Action handlers for PaperworkPanel ---
  const handlePaperworkAction = (action: string, payload?: any) => {
    // Example: trigger chat commands or update deal session
    if (action === "add-trade") setInput("Add trade-in to deal");
    if (action === "update-price") setInput("Update price to ...");
    if (action === "generate-paperwork") setInput("Generate paperwork");
    if (action === "print-all" && pdfUrl) window.open(pdfUrl, "_blank");
  };

  // Responsive: show as drawer/tab on mobile, three-panel on desktop, two-panel on tablet
  const [windowWidth, setWindowWidth] = useState(typeof window !== "undefined" ? window.innerWidth : 1200);
  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);
  const isMobile = windowWidth < 768;
  const isTablet = windowWidth >= 768 && windowWidth < 1024;
  const isDesktop = windowWidth >= 1024;

  return (
    <div className="h-full w-full bg-imperial-bg-light dark:bg-imperial-bg-dark">
      {isDesktop ? (
        <Allotment defaultSizes={[35, 30, 35]} minSize={280} className="h-full w-full">
          <Allotment.Pane>
            <div className="panel h-full bg-imperial-bg-light dark:bg-imperial-bg-dark flex flex-col">
              {/* Welcome Banner */}
              {greeting && (
                <div className="mb-4 rounded-xl bg-gradient-to-r from-imperial-primary/10 to-imperial-primary/0 px-4 py-3 text-imperial-primary dark:text-imperial-primary-light font-semibold shadow-sm">
                  {greeting}
                  {interests.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-2">
                      {interests.map((interest) => (
                        <span key={interest} className="rounded-full bg-imperial-primary/10 px-3 py-1 text-xs font-medium text-imperial-primary dark:text-imperial-primary-light border border-imperial-primary/20">
                          {interest}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Message List */}
              <div className="flex-1 overflow-y-auto pr-2" style={{ minHeight: 0 }}>
                {messages.map((msg, idx) => (
                  <MessageBubble
                    key={idx}
                    role={msg.role}
                    content={msg.content}
                    source={msg.source}
                    metadata={msg.metadata}
                    feedback={msg.feedback}
                    onFeedback={(rating) => handleFeedback(idx, rating)}
                    error={Boolean(msg.error)}
                  />
                ))}
                {showRetry && (
                  <div className="flex justify-center mt-2">
                    <button
                      className="rounded-full bg-yellow-100 px-4 py-2 text-sm font-semibold text-yellow-700 border border-yellow-300 shadow hover:bg-yellow-200 focus:outline-none focus:ring-2 focus:ring-yellow-400"
                      onClick={handleRetry}
                      aria-label="Retry last message"
                    >
                      Retry
                    </button>
                  </div>
                )}
                {loading && (
                  <div className="flex justify-start mt-2">
                    <div className="flex items-center gap-1 px-4 py-2">
                      <span className="inline-block w-2 h-2 bg-imperial-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                      <span className="inline-block w-2 h-2 bg-imperial-primary/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                      <span className="inline-block w-2 h-2 bg-imperial-primary/30 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                      <span className="ml-2 text-xs text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Assistant is typing…</span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Quick Replies */}
              <div className="mt-2 flex flex-wrap gap-2">
                {getQuickReplies().map(({ label, icon, prompt }) => (
                  <button
                    key={label}
                    type="button"
                    className="rounded-full bg-imperial-primary/10 px-4 py-1 text-xs font-semibold text-imperial-primary dark:text-imperial-primary-light border border-imperial-primary/20 hover:bg-imperial-primary/20 focus:outline-none focus:ring-2 focus:ring-imperial-primary flex items-center gap-1"
                    tabIndex={0}
                    aria-label={`Quick reply: ${label}`}
                    onClick={() => setInput(prompt)}
                  >
                    <span>{icon}</span>
                    {label}
                  </button>
                ))}
              </div>

              {/* Input Area */}
              <form
                className="mt-4 flex items-end gap-2"
                onSubmit={e => {
                  e.preventDefault();
                  handleSend();
                }}
                role="search"
                aria-label="Send a message to Imperial Assistant"
              >
                <textarea
                  className="flex-1 resize-none rounded-xl border border-imperial-border dark:border-imperial-border-dark bg-white dark:bg-imperial-surface-dark px-4 py-2 text-sm text-imperial-text dark:text-imperial-text-dark shadow focus:border-imperial-primary focus:ring-2 focus:ring-imperial-primary/30 focus:outline-none"
                  rows={1}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  placeholder="Type your question..."
                  aria-label="Message input"
                  aria-required="true"
                  aria-disabled={loading}
                  tabIndex={0}
                  disabled={loading}
                  required
                />
                <button
                  type="button"
                  className="rounded-xl border border-imperial-border px-4 py-2 text-sm font-semibold text-imperial-text hover:bg-imperial-surface focus:outline-none focus:ring-2 focus:ring-imperial-primary"
                  onClick={handleVoiceInput}
                  aria-label="Use voice input"
                  tabIndex={0}
                >
                  Voice
                </button>
                <button
                  type="submit"
                  className="rounded-xl bg-imperial-primary px-5 py-2 text-sm font-bold text-white shadow hover:bg-imperial-primary-dark focus:outline-none focus:ring-2 focus:ring-imperial-primary"
                  disabled={loading || !input.trim()}
                  aria-label="Send message"
                  tabIndex={0}
                >
                  Send
                </button>
              </form>
            </div>
          </Allotment.Pane>
          <Allotment.Pane preferredSize={30} minSize={320} maxSize={480}>
            <div className="panel h-full bg-white dark:bg-imperial-surface-dark border-l border-imperial-border dark:border-imperial-border-dark">
              <VisualizationsPanel stockNumber={chatContext?.stock_number || chatContext?.vehicle?.stock_number} />
            </div>
          </Allotment.Pane>
          <Allotment.Pane preferredSize={35} minSize={320} maxSize={480}>
            <div className="panel h-full bg-imperial-surface dark:bg-imperial-surface-dark border-l border-imperial-border dark:border-imperial-border-dark">
              <PaperworkPanel
                dealSession={dealSession}
                onAction={handlePaperworkAction}
                pdfUrl={pdfUrl}
                validationErrors={validationErrors}
              />
            </div>
          </Allotment.Pane>
        </Allotment>
      ) : isTablet ? (
        <div className="flex h-full w-full">
          <div className="flex-1 min-w-0 flex flex-col h-full max-h-[calc(100vh-8rem)] bg-imperial-bg-light dark:bg-imperial-bg-dark">
            {/* Welcome Banner */}
            {greeting && (
              <div className="mb-4 rounded-xl bg-gradient-to-r from-imperial-primary/10 to-imperial-primary/0 px-4 py-3 text-imperial-primary dark:text-imperial-primary-light font-semibold shadow-sm">
                {greeting}
                {interests.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-2">
                    {interests.map((interest) => (
                      <span key={interest} className="rounded-full bg-imperial-primary/10 px-3 py-1 text-xs font-medium text-imperial-primary dark:text-imperial-primary-light border border-imperial-primary/20">
                        {interest}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
            {/* Message List */}
            <div className="flex-1 overflow-y-auto pr-2" style={{ minHeight: 0 }}>
              {messages.map((msg, idx) => (
                <MessageBubble
                  key={idx}
                  role={msg.role}
                  content={msg.content}
                  source={msg.source}
                  metadata={msg.metadata}
                  feedback={msg.feedback}
                  onFeedback={(rating) => handleFeedback(idx, rating)}
                />
              ))}
              {loading && (
                <div className="flex justify-start mt-2">
                  <div className="animate-pulse rounded-xl bg-imperial-surface dark:bg-imperial-surface-dark px-4 py-2 text-sm text-imperial-text-secondary dark:text-imperial-text-secondary-dark shadow">
                    <span className="inline-block w-2 h-2 bg-imperial-primary rounded-full mr-1"></span>
                    <span className="inline-block w-2 h-2 bg-imperial-primary/60 rounded-full mr-1"></span>
                    <span className="inline-block w-2 h-2 bg-imperial-primary/30 rounded-full"></span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            {/* Quick Replies */}
            <div className="mt-2 flex flex-wrap gap-2">
              {["Finance", "Trade-In", "Compare"].map((label) => (
                <button
                  key={label}
                  type="button"
                  className="rounded-full bg-imperial-primary/10 px-4 py-1 text-xs font-semibold text-imperial-primary dark:text-imperial-primary-light border border-imperial-primary/20 hover:bg-imperial-primary/20 focus:outline-none focus:ring-2 focus:ring-imperial-primary"
                  onClick={() => setInput(label === "Compare" ? "Compare top options for value and reliability." : label === "Finance" ? "Help me compare financing options for this vehicle." : "I want a trade-in estimate and next steps.")}
                >
                  {label}
                </button>
              ))}
            </div>
            {/* Input Area */}
            <form
              className="mt-4 flex items-end gap-2"
              onSubmit={e => {
                e.preventDefault();
                handleSend();
              }}
              role="search"
              aria-label="Send a message to Imperial Assistant"
            >
              <textarea
                className="flex-1 resize-none rounded-xl border border-imperial-border dark:border-imperial-border-dark bg-white dark:bg-imperial-surface-dark px-4 py-2 text-sm text-imperial-text dark:text-imperial-text-dark shadow focus:border-imperial-primary focus:ring-2 focus:ring-imperial-primary/30"
                rows={1}
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="Type your question..."
                aria-label="Message input"
                disabled={loading}
                required
              />
              <button
                type="submit"
                className="rounded-xl bg-imperial-primary px-5 py-2 text-sm font-bold text-white shadow hover:bg-imperial-primary-dark focus:outline-none focus:ring-2 focus:ring-imperial-primary"
                disabled={loading || !input.trim()}
                aria-label="Send message"
              >
                Send
              </button>
            </form>
          </div>
          <div className="w-[40%] min-w-[280px] max-w-[400px] border-l border-imperial-border dark:border-imperial-border-dark h-full">
            <VisualizationsPanel stockNumber={chatContext?.stock_number || chatContext?.vehicle?.stock_number} />
          </div>
        </div>
      ) : (
        <div className="flex flex-col h-full w-full bg-imperial-bg-light dark:bg-imperial-bg-dark">
          {/* Mobile: tab switcher */}
          <div className="flex border-b border-imperial-border dark:border-imperial-border-dark bg-imperial-bg-light dark:bg-imperial-bg-dark">
            <button className="flex-1 py-2 font-semibold border-b-2 border-imperial-primary bg-imperial-bg-light dark:bg-imperial-bg-dark text-imperial-primary dark:text-imperial-primary-light">Chat</button>
            <button className="flex-1 py-2 font-semibold border-b-2 border-transparent bg-imperial-bg-light dark:bg-imperial-bg-dark text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Paperwork</button>
            <button className="flex-1 py-2 font-semibold border-b-2 border-transparent bg-imperial-bg-light dark:bg-imperial-bg-dark text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Visuals</button>
          </div>
          {/* Chat UI (default tab) */}
          <div className="flex-1 overflow-y-auto px-2 pb-32">
            {greeting && (
              <div className="mb-4 rounded-xl bg-gradient-to-r from-imperial-primary/10 to-imperial-primary/0 px-4 py-3 text-imperial-primary dark:text-imperial-primary-light font-semibold shadow-sm">
                {greeting}
                {interests.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-2">
                    {interests.map((interest) => (
                      <span key={interest} className="rounded-full bg-imperial-primary/10 px-3 py-1 text-xs font-medium text-imperial-primary dark:text-imperial-primary-light border border-imperial-primary/20">
                        {interest}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
            {messages.map((msg, idx) => (
              <MessageBubble
                key={idx}
                role={msg.role}
                content={msg.content}
                source={msg.source}
                metadata={msg.metadata}
                feedback={msg.feedback}
                onFeedback={(rating) => handleFeedback(idx, rating)}
              />
            ))}
            {loading && (
              <div className="flex justify-start mt-2">
                <div className="animate-pulse rounded-xl bg-imperial-surface dark:bg-imperial-surface-dark px-4 py-2 text-sm text-imperial-text-secondary dark:text-imperial-text-secondary-dark shadow">
                  <span className="inline-block w-2 h-2 bg-imperial-primary rounded-full mr-1"></span>
                  <span className="inline-block w-2 h-2 bg-imperial-primary/60 rounded-full mr-1"></span>
                  <span className="inline-block w-2 h-2 bg-imperial-primary/30 rounded-full"></span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
            {/* Quick Replies */}
            <div className="mt-2 flex flex-wrap gap-2 pb-2">
              {["Finance", "Trade-In", "Compare"].map((label) => (
                <button
                  key={label}
                  type="button"
                  className="rounded-full bg-imperial-primary/10 px-4 py-1 text-xs font-semibold text-imperial-primary dark:text-imperial-primary-light border border-imperial-primary/20 hover:bg-imperial-primary/20 focus:outline-none focus:ring-2 focus:ring-imperial-primary"
                  onClick={() => setInput(label === "Compare" ? "Compare top options for value and reliability." : label === "Finance" ? "Help me compare financing options for this vehicle." : "I want a trade-in estimate and next steps.")}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {/* Input Area (fixed bottom) */}
          <form
            className="fixed bottom-0 left-0 right-0 z-50 flex items-end gap-2 bg-imperial-bg-light dark:bg-imperial-bg-dark px-2 py-3 border-t border-imperial-border dark:border-imperial-border-dark"
            onSubmit={e => {
              e.preventDefault();
              handleSend();
            }}
            role="search"
            aria-label="Send a message to Imperial Assistant"
          >
            <textarea
              className="flex-1 resize-none rounded-xl border border-imperial-border dark:border-imperial-border-dark bg-white dark:bg-imperial-surface-dark px-4 py-2 text-sm text-imperial-text dark:text-imperial-text-dark shadow focus:border-imperial-primary focus:ring-2 focus:ring-imperial-primary/30"
              rows={1}
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Type your question..."
              aria-label="Message input"
              disabled={loading}
              required
            />
            <button
              type="submit"
              className="rounded-xl bg-imperial-primary px-5 py-2 text-sm font-bold text-white shadow hover:bg-imperial-primary-dark focus:outline-none focus:ring-2 focus:ring-imperial-primary"
              disabled={loading || !input.trim()}
              aria-label="Send message"
            >
              Send
            </button>
          </form>
          {/* VisualizationsPanel as swipeable card above input (mobile) */}
          <div className="fixed bottom-20 left-0 right-0 z-40">
            <VisualizationsPanel stockNumber={chatContext?.stock_number || chatContext?.vehicle?.stock_number} />
          </div>
          {/* PaperworkPanel as drawer or below */}
          <div className="fixed bottom-0 left-0 right-0 z-30 bg-imperial-surface dark:bg-imperial-surface-dark border-t border-imperial-border dark:border-imperial-border-dark shadow-lg">
            <PaperworkPanel
              dealSession={dealSession}
              onAction={handlePaperworkAction}
              pdfUrl={pdfUrl}
              validationErrors={validationErrors}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function getQuickReplies() {
  return [
    { label: "Finance", icon: "💸", prompt: "Help me compare financing options for this vehicle." },
    { label: "Trade-In", icon: "🔄", prompt: "I want a trade-in estimate and next steps." },
    { label: "Compare", icon: "📊", prompt: "Compare top options for value and reliability." },
    { label: "Payment", icon: "🧾", prompt: "Estimate monthly payment for this vehicle." },
    { label: "Specs", icon: "🚗", prompt: "Show me detailed specs for this vehicle." },
  ];
}

function MessageBubble({ role, content, source, metadata, feedback, onFeedback, error, renderComparison, sourceLabel }: {
  role: "user" | "ai";
  content: string;
  source?: string;
  metadata?: any;
  feedback?: "up" | "down" | null;
  onFeedback?: (rating: "up" | "down") => void;
  error?: boolean;
  renderComparison?: (metadata?: AskResponseDetailed["metadata"]) => React.ReactNode;
  sourceLabel?: (source?: string) => string;
}) {
  const isUser = role === "user";
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };
  const handleEscalate = () => alert("Escalation requested (demo)");
  const handleRetry = () => alert("Retry requested (demo)");
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-2`}>
      <div
        className={`relative max-w-[80%] rounded-2xl px-4 py-2 text-sm shadow ${isUser
          ? "bg-imperial-primary text-white self-end"
          : error ? "bg-yellow-100 text-yellow-800 border border-yellow-400" : "bg-imperial-surface dark:bg-imperial-surface-dark text-imperial-text dark:text-imperial-text-dark border border-imperial-border/40"}
        `}
        aria-live={isUser ? undefined : "polite"}
        aria-label={isUser ? "Your message" : error ? "Error message" : "Imperial Assistant reply"}
      >
        {isUser ? (
          <span>{content}</span>
        ) : (
          <ReactMarkdown
            components={{
              a: ({ node: _node, ...props }) => (
                <a {...props} target="_blank" rel="noreferrer" className="text-imperial-primary underline" />
              ),
            }}
          >
            {content}
          </ReactMarkdown>
        )}
        {metadata?.comparison && renderComparison && (
          <div className="mt-2">{renderComparison(metadata)}</div>
        )}
        {source && !isUser && sourceLabel && (
          <div className="mt-1 text-xs text-imperial-text-secondary dark:text-imperial-text-secondary-dark">{sourceLabel(source)}</div>
        )}
        {!isUser && (
          <div className="absolute top-1 right-2 flex gap-1 opacity-80">
            <button
              className="rounded-full px-2 py-1 text-xs font-semibold border border-slate-200 text-slate-500 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-imperial-primary"
              onClick={handleCopy}
              aria-label="Copy message"
            >{copied ? "✓" : "⧉"}</button>
            <button
              className="rounded-full px-2 py-1 text-xs font-semibold border border-blue-200 text-blue-500 hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-imperial-primary"
              onClick={handleEscalate}
              aria-label="Escalate to human"
            >🚩</button>
            <button
              className="rounded-full px-2 py-1 text-xs font-semibold border border-yellow-200 text-yellow-500 hover:bg-yellow-50 focus:outline-none focus:ring-2 focus:ring-imperial-primary"
              onClick={handleRetry}
              aria-label="Retry message"
            >⟳</button>
          </div>
        )}
        {!isUser && typeof feedback !== "undefined" && (
          <div className="mt-2 flex gap-2">
            <button
              className={`rounded-full px-2 py-1 text-xs font-semibold border ${feedback === "up" ? "bg-green-100 border-green-400 text-green-700" : "border-slate-200 text-slate-500 hover:bg-green-50"}`}
              onClick={() => onFeedback && onFeedback("up")}
              aria-label="Thumbs up"
              disabled={!!feedback}
            >👍</button>
            <button
              className={`rounded-full px-2 py-1 text-xs font-semibold border ${feedback === "down" ? "bg-red-100 border-red-400 text-red-700" : "border-slate-200 text-slate-500 hover:bg-red-50"}`}
              onClick={() => onFeedback && onFeedback("down")}
              aria-label="Thumbs down"
              disabled={!!feedback}
            >👎</button>
          </div>
        )}
      </div>
    </div>
  );
}

