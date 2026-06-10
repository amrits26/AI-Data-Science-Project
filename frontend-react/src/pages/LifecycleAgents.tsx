import { useEffect, useState } from "react"

import { api } from "../services/api"
import type { LeadContact, LeadSummary } from "../types"

const CONTACT_ICONS = ["📞", "📧", "💬", "📱", "🤝"]

function tierBadge(tier: LeadSummary["tier"]): string {
  if (tier === "hot") return "bg-red-100 text-red-700"
  if (tier === "warm") return "bg-amber-100 text-amber-700"
  return "bg-blue-100 text-blue-700"
}

export default function LifecycleAgents() {
  const [leads, setLeads] = useState<LeadSummary[]>([])
  const [contactsMap, setContactsMap] = useState<Record<number, LeadContact[]>>({})
  const [status, setStatus] = useState("")
  const [error, setError] = useState("")

  const loadLeads = async () => {
    setError("")
    try {
      const rows = await api.getLeadsSummary(25)
      setLeads(rows)

      const details = await Promise.all(
        rows.map(async (lead) => {
          const contacts = await api.getLeadContacts(lead.customer_id)
          return [lead.customer_id, contacts] as const
        })
      )

      const next: Record<number, LeadContact[]> = {}
      details.forEach(([id, rows]) => {
        next[id] = rows
      })
      setContactsMap(next)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Unable to load lifecycle data right now.")
    }
  }

  useEffect(() => {
    void loadLeads()
  }, [])

  const addContact = async (customerId: number, contactType: LeadContact["contact_type"]) => {
    setStatus("")
    setError("")
    try {
      await api.logLeadContact(customerId, {
        contact_type: contactType,
        outcome: "completed",
        notes: `Logged from Lifecycle Agents UI as ${contactType}`,
      })
      await api.scoreLead(customerId, { auto_schedule: true })
      await loadLeads()
      setStatus(`Logged ${contactType} for customer #${customerId}.`)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || `Unable to log ${contactType} right now.`)
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="m-0 text-xl font-bold text-slate-900">Lifecycle Agents</h2>
      <p className="mt-1 text-sm text-slate-600">Tier cadence targets: Hot 24h, Warm 3 days, Cold 7 days.</p>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-red-200 bg-red-50 p-3">
          <p className="text-xs uppercase tracking-wide text-red-600">Hot Leads</p>
          <p className="mt-1 text-2xl font-bold text-red-700">24h</p>
          <p className="text-xs text-red-600">Cadence target</p>
        </div>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <p className="text-xs uppercase tracking-wide text-amber-700">Warm Leads</p>
          <p className="mt-1 text-2xl font-bold text-amber-700">3d</p>
          <p className="text-xs text-amber-700">Cadence target</p>
        </div>
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
          <p className="text-xs uppercase tracking-wide text-blue-700">Cold Leads</p>
          <p className="mt-1 text-2xl font-bold text-blue-700">7d</p>
          <p className="text-xs text-blue-700">Cadence target</p>
        </div>
      </div>

      {status && <p className="mt-3 text-sm font-semibold text-slate-700">{status}</p>}
      {error && <p className="mt-3 text-sm font-semibold text-imperial-danger">{error}</p>}

      <div className="mt-4 space-y-3">
        {leads.map((lead) => {
          const contacts = contactsMap[lead.customer_id] || []
          const progress = Math.min(contacts.length, 5)
          return (
            <article key={lead.customer_id} className="rounded-lg border border-slate-200 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-base font-bold text-slate-900">{lead.name || `Lead #${lead.customer_id}`}</p>
                  <p className="text-xs text-slate-500">ID {lead.customer_id} • Score {lead.score}</p>
                </div>
                <span className={`rounded-full px-2 py-1 text-xs font-bold uppercase ${tierBadge(lead.tier)}`}>
                  {lead.tier}
                </span>
              </div>

              <div className="mt-3 flex items-center gap-2" aria-label={`${progress} of 5 contacts completed`}>
                {CONTACT_ICONS.map((icon, idx) => (
                  <span
                    key={`${lead.customer_id}-${idx}`}
                    className={`inline-flex h-8 w-8 items-center justify-center rounded-full border text-sm ${idx < progress ? "border-imperial-primary bg-red-50" : "border-slate-300 bg-slate-50 opacity-60"}`}
                  >
                    {icon}
                  </span>
                ))}
                <span className="ml-2 text-xs font-semibold text-slate-600">{progress}/5 contacts</span>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" onClick={() => addContact(lead.customer_id, "call")} className="rounded-md border border-slate-300 px-2 py-1 text-xs font-semibold">Log Call</button>
                <button type="button" onClick={() => addContact(lead.customer_id, "email")} className="rounded-md border border-slate-300 px-2 py-1 text-xs font-semibold">Log Email</button>
                <button type="button" onClick={() => addContact(lead.customer_id, "text")} className="rounded-md border border-slate-300 px-2 py-1 text-xs font-semibold">Log Text</button>
                <button type="button" onClick={() => addContact(lead.customer_id, "voicemail")} className="rounded-md border border-slate-300 px-2 py-1 text-xs font-semibold">Log Voicemail</button>
                <button type="button" onClick={() => addContact(lead.customer_id, "in-person")} className="rounded-md border border-slate-300 px-2 py-1 text-xs font-semibold">Log In-person</button>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
