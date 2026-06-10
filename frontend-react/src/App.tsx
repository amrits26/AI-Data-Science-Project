import { useEffect, useMemo, useState } from "react"

import FloatingChatBubble from "./components/FloatingChatBubble"
import { useMode } from "./context/ModeContext"
import ActivityDashboard from "./pages/ActivityDashboard"
import CarDatabase from "./pages/CarDatabase"
import Chatbot from "./pages/Chatbot"
import FinancialTools from "./pages/FinancialTools"
import FollowUp from "./pages/FollowUp"
import LifecycleAgents from "./pages/LifecycleAgents"
import Paperwork from "./pages/Paperwork"
import ScheduleTestDrive from "./pages/ScheduleTestDrive"
import { api } from "./services/api"

type TabKey =
  | "chatbot"
  | "inventory"
  | "payment"
  | "testdrive"
  | "paperwork"
  | "followup"
  | "lifecycle"
  | "activity"

const CUSTOMER_TABS: Array<{ key: TabKey; label: string; hint: string }> = [
  { key: "chatbot", label: "Chat", hint: "Ask anything about inventory, financing, and service" },
  { key: "inventory", label: "Inventory", hint: "Browse featured vehicles and ask AI about each listing" },
  { key: "payment", label: "Payment Estimator", hint: "Estimate financing options and compare ownership paths" },
  { key: "testdrive", label: "Schedule Test Drive", hint: "Book a test drive in a few steps" },
]

const SALES_TABS: Array<{ key: TabKey; label: string; hint: string }> = [
  { key: "paperwork", label: "Paperwork", hint: "Upload forms and extract fields with EasyOCR" },
  { key: "followup", label: "Follow-up Logs", hint: "Send one-button multichannel follow-up by preference" },
  { key: "lifecycle", label: "Lifecycle Agents", hint: "Lead cadence and lifecycle automation controls" },
  { key: "activity", label: "Activity Dashboard", hint: "Track outreach momentum and daily team activity" },
]

function App() {
  const { mode, setMode, isSalespersonMode } = useMode()
  const [activeTab, setActiveTab] = useState<TabKey>("chatbot")
  const [prefilledPrompt, setPrefilledPrompt] = useState("")
  const [showPinPrompt, setShowPinPrompt] = useState(false)
  const [pinInput, setPinInput] = useState("")
  const [pinError, setPinError] = useState("")
  const [pinLoading, setPinLoading] = useState(false)
  const [trustBadgeText, setTrustBadgeText] = useState("Trusted by Imperial families")

  const tabs = useMemo(
    () => (isSalespersonMode ? SALES_TABS : CUSTOMER_TABS),
    [isSalespersonMode]
  )
  const active = useMemo(() => tabs.find((x) => x.key === activeTab) || tabs[0], [activeTab, tabs])

  useEffect(() => {
    if (!tabs.some((tab) => tab.key === activeTab)) {
      setActiveTab(tabs[0].key)
    }
  }, [activeTab, tabs])

  useEffect(() => {
    const loadTrustBadge = async () => {
      try {
        const stats = await api.getCustomerCountStats()
        setTrustBadgeText(stats.badge_text)
      } catch {
        setTrustBadgeText("Trusted by Imperial families")
      }
    }
    void loadTrustBadge()
  }, [])

  const switchToCustomerMode = () => {
    setMode("customer")
    setActiveTab("chatbot")
  }

  const requestSalespersonMode = () => {
    setPinError("")
    setPinInput("")
    setShowPinPrompt(true)
  }

  const unlockSalespersonMode = async () => {
    if (!pinInput.trim()) {
      setPinError("PIN is required")
      return
    }
    setPinLoading(true)
    setPinError("")
    try {
      const ok = await api.verifySalespersonPin(pinInput.trim())
      if (!ok) {
        setPinError("Invalid PIN")
        return
      }
      setMode("salesperson")
      setActiveTab("paperwork")
      setShowPinPrompt(false)
      setPinInput("")
    } catch {
      setPinError("Unable to validate PIN")
    } finally {
      setPinLoading(false)
    }
  }

  const openChatWithPrompt = (prompt: string) => {
    setMode("customer")
    setActiveTab("chatbot")
    setPrefilledPrompt(prompt)
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      {/* Skip to main content link for keyboard/screen-reader users */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 bg-imperial-primary text-white px-3 py-2 rounded z-50 font-semibold"
      >
        Skip to main content
      </a>

      <header className="bg-white border-b border-slate-200 sticky top-0 z-20" role="banner">
        <div className="mx-auto max-w-7xl px-4 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs tracking-[0.2em] uppercase text-slate-500">Imperial Cars AI</p>
              <h1 className="text-2xl md:text-3xl font-bold">Dealership Command Center</h1>
            </div>
            <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-1">
              <button
                type="button"
                onClick={switchToCustomerMode}
                className={`rounded-md px-3 py-1.5 text-xs font-bold ${mode === "customer" ? "bg-imperial-primary text-white" : "text-slate-700"}`}
              >
                Customer Mode
              </button>
              <button
                type="button"
                onClick={requestSalespersonMode}
                className={`rounded-md px-3 py-1.5 text-xs font-bold ${mode === "salesperson" ? "bg-imperial-secondary text-white" : "text-slate-700"}`}
              >
                Salesperson Mode
              </button>
            </div>
          </div>
          <p className="text-sm text-slate-600 mt-1" aria-live="polite">{active?.hint}</p>
          <p className="mt-1 inline-flex rounded-full border border-green-200 bg-green-50 px-3 py-1 text-xs font-semibold text-green-800" aria-label="Trust badge">
            {trustBadgeText}
          </p>
        </div>
        <nav className="mx-auto max-w-7xl px-4 pb-4" aria-label="Application sections">
          <div
            role="tablist"
            aria-label="Application sections"
            className={`grid gap-2 ${tabs.length === 4 ? "grid-cols-2 md:grid-cols-4" : "grid-cols-2 md:grid-cols-4"}`}
          >
            {tabs.map((tab) => (
              activeTab === tab.key ? (
                <button
                  key={tab.key}
                  role="tab"
                  aria-selected="true"
                  aria-controls={`panel-${tab.key}`}
                  id={`tab-${tab.key}`}
                  onClick={() => setActiveTab(tab.key)}
                  className="rounded-lg px-3 py-2 text-sm font-semibold border transition bg-imperial-secondary text-white border-imperial-secondary"
                >
                  {tab.label}
                </button>
              ) : (
                <button
                  key={tab.key}
                  role="tab"
                  aria-selected="false"
                  aria-controls={`panel-${tab.key}`}
                  id={`tab-${tab.key}`}
                  onClick={() => setActiveTab(tab.key)}
                  className="rounded-lg px-3 py-2 text-sm font-semibold border transition bg-white text-slate-700 border-slate-300 hover:border-imperial-primary"
                >
                  {tab.label}
                </button>
              )
            ))}
          </div>
        </nav>
      </header>

      <main id="main-content" role="main" className="mx-auto max-w-7xl px-4 py-6">
        {tabs.map((tab) => (
          <div
            key={tab.key}
            role="tabpanel"
            id={`panel-${tab.key}`}
            aria-labelledby={`tab-${tab.key}`}
            hidden={activeTab !== tab.key}
            tabIndex={0}
          >
            {activeTab === tab.key && (
              <>
                {tab.key === "chatbot" && <Chatbot prefilledPrompt={prefilledPrompt} />}
                {tab.key === "inventory" && <CarDatabase onAskAI={openChatWithPrompt} />}
                {tab.key === "payment" && <FinancialTools />}
                {tab.key === "testdrive" && <ScheduleTestDrive />}
                {tab.key === "paperwork" && <Paperwork />}
                {tab.key === "followup" && <FollowUp />}
                {tab.key === "lifecycle" && <LifecycleAgents />}
                {tab.key === "activity" && <ActivityDashboard />}
              </>
            )}
          </div>
        ))}
      </main>

      <FloatingChatBubble onRequestOpenFullChat={openChatWithPrompt} />

      {showPinPrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label="Salesperson PIN">
          <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-4 shadow-2xl">
            <h2 className="m-0 text-lg font-bold text-slate-900">Enter Salesperson PIN</h2>
            <p className="mt-1 text-sm text-slate-600">Use your secure PIN to unlock sales tools.</p>
            <input
              type="password"
              value={pinInput}
              onChange={(e) => setPinInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") unlockSalespersonMode()
                if (e.key === "Escape") setShowPinPrompt(false)
              }}
              className="mt-3 rounded-lg border border-slate-300 px-3 py-2"
              aria-label="Salesperson PIN input"
              placeholder="PIN"
            />
            {pinError && <p className="mt-2 text-sm text-imperial-danger">{pinError}</p>}
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setShowPinPrompt(false)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold">
                Cancel
              </button>
              <button
                type="button"
                onClick={unlockSalespersonMode}
                disabled={pinLoading}
                className="rounded-lg bg-imperial-secondary px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {pinLoading ? "Validating..." : "Unlock"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
