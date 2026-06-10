import { useEffect, useState } from "react"

import { api } from "../services/api"
import type { ChannelPref, FollowupResponse } from "../types"

const CHANNELS: ChannelPref["channel"][] = ["sms", "whatsapp", "email", "voice"]

export default function FollowUp() {
  const [customerId, setCustomerId] = useState(1)
  const [prefs, setPrefs] = useState<ChannelPref[]>(
    CHANNELS.map((c) => ({ channel: c, is_enabled: c === "sms", contact_value: "" }))
  )
  const [message, setMessage] = useState("")
  const [result, setResult] = useState<FollowupResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  const refresh = async () => {
    try {
      const rows = await api.getCustomerPreferences(customerId)
      if (rows.length) {
        setPrefs(
          CHANNELS.map((ch) => {
            const found = rows.find((r) => r.channel === ch)
            return found || { channel: ch, is_enabled: false, contact_value: "" }
          })
        )
      }
    } catch {
      // keep defaults when customer has no saved rows yet
    }
  }

  useEffect(() => {
    refresh()
  }, [customerId])

  const updatePref = (channel: ChannelPref["channel"], patch: Partial<ChannelPref>) => {
    setPrefs((prev) => prev.map((p) => (p.channel === channel ? { ...p, ...patch } : p)))
  }

  const savePrefs = async () => {
    setSaving(true)
    try {
      const updated = await api.saveCustomerPreferences(customerId, prefs)
      setPrefs(
        CHANNELS.map((ch) => {
          const found = updated.find((r) => r.channel === ch)
          return found || { channel: ch, is_enabled: false, contact_value: "" }
        })
      )
    } finally {
      setSaving(false)
    }
  }

  const send = async () => {
    setLoading(true)
    try {
      const r = await api.sendFollowup(customerId, message || undefined)
      setResult(r)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="text-lg font-semibold">Customer Communication Preferences</h3>
        <p className="text-sm text-slate-600 mt-1">Enable only channels approved by the customer.</p>

        <div className="mt-3">
          <label className="text-sm text-slate-700">Customer ID</label>
          <input
            title="Customer ID"
            type="number"
            value={customerId}
            onChange={(e) => setCustomerId(Number(e.target.value || 1))}
            className="mt-1 rounded border px-3 py-2"
          />
        </div>

        <div className="mt-4 space-y-3">
          {prefs.map((pref) => (
            <div key={pref.channel} className="rounded-lg border border-slate-200 p-3">
              <div className="flex items-center justify-between">
                <p className="font-semibold uppercase text-sm">{pref.channel}</p>
                <input
                  title={`${pref.channel} enabled`}
                  type="checkbox"
                  checked={Boolean(pref.is_enabled)}
                  onChange={(e) => updatePref(pref.channel, { is_enabled: e.target.checked })}
                />
              </div>
              <input
                title={`${pref.channel} contact value`}
                type="text"
                value={pref.contact_value || ""}
                onChange={(e) => updatePref(pref.channel, { contact_value: e.target.value })}
                placeholder={pref.channel === "email" ? "name@example.com" : "+15085551234"}
                className="mt-2 rounded border px-3 py-2 w-full"
              />
            </div>
          ))}
        </div>

        <button onClick={savePrefs} className="mt-3 rounded-lg bg-imperial-primary text-white px-4 py-2 font-semibold" disabled={saving}>
          {saving ? "Saving..." : "Save Preferences"}
        </button>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="text-lg font-semibold">One-Button Follow-up</h3>
        <textarea
          className="mt-3 w-full rounded border p-3 h-24"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Optional custom message. Leave blank for AI-generated message."
        />

        <button onClick={send} className="mt-3 rounded-lg bg-imperial-secondary text-white px-4 py-2 font-semibold" disabled={loading}>
          {loading ? "Sending..." : "Send Follow-up"}
        </button>

        <pre className="mt-4 text-xs bg-slate-900 text-slate-100 p-3 rounded-lg overflow-auto max-h-[300px]">
          {JSON.stringify(result || { status: "idle", note: "Send a follow-up to see channel results." }, null, 2)}
        </pre>
      </div>
    </section>
  )
}
