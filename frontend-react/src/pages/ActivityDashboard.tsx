import { useEffect, useMemo, useState } from "react"

import { api } from "../services/api"
import type { SalesDashboardMe } from "../types"

type GoalForm = {
  calls: number
  texts: number
  emails: number
  appointments: number
}

function barWidthClass(percent: number): string {
  if (percent < 10) return "w-[10%]"
  if (percent < 20) return "w-[20%]"
  if (percent < 30) return "w-[30%]"
  if (percent < 40) return "w-[40%]"
  if (percent < 50) return "w-[50%]"
  if (percent < 60) return "w-[60%]"
  if (percent < 70) return "w-[70%]"
  if (percent < 80) return "w-[80%]"
  if (percent < 90) return "w-[90%]"
  return "w-full"
}

export default function ActivityDashboard() {
  const [salespersonId, setSalespersonId] = useState<number>(1)
  const [goalForm, setGoalForm] = useState<GoalForm>({ calls: 20, texts: 30, emails: 10, appointments: 8 })
  const [activity, setActivity] = useState<{ actual: GoalForm; goals: GoalForm; progress_percent: GoalForm } | null>(null)
  const [dashboard, setDashboard] = useState<SalesDashboardMe | null>(null)
  const [status, setStatus] = useState("")
  const [error, setError] = useState("")

  const load = async () => {
    setError("")
    try {
      const goals = await api.getDailyGoals(String(salespersonId))
      setGoalForm({
        calls: goals.goals.calls,
        texts: goals.goals.texts,
        emails: goals.goals.emails,
        appointments: goals.goals.appointments,
      })

      const a = await api.getActivityToday(salespersonId)
      setActivity({
        actual: a.actual,
        goals: a.goals,
        progress_percent: a.progress_percent,
      })

      const d = await api.getDashboardMe(salespersonId > 0 ? { salesperson_id: salespersonId } : undefined)
      setDashboard(d)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Unable to load dashboard data right now.")
    }
  }

  useEffect(() => {
    void load()
  }, [salespersonId])

  const saveGoals = async () => {
    setError("")
    try {
      await api.setDailyGoals({
        salesperson_id: String(salespersonId),
        call_goal: goalForm.calls,
        text_goal: goalForm.texts,
        email_goal: goalForm.emails,
        appointment_goal: goalForm.appointments,
      })
      await load()
      setStatus("Goals updated for today.")
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Unable to save goals right now.")
    }
  }

  const overallPercent = useMemo(() => {
    if (!activity) return 0
    const vals = [activity.progress_percent.calls, activity.progress_percent.texts, activity.progress_percent.emails, activity.progress_percent.appointments]
    return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length)
  }, [activity])

  const showConfetti = overallPercent >= 100
  const ytdWidth = barWidthClass(dashboard?.ytd_progress_percent || 0)

  return (
    <section className="relative rounded-xl border border-imperial-border dark:border-imperial-border-dark bg-imperial-surface dark:bg-imperial-surface-dark p-4 overflow-hidden">
      {showConfetti && (
        <div className="pointer-events-none absolute inset-0" aria-hidden="true">
          <div className="confetti-celebration" />
        </div>
      )}

      <h2 className="m-0 text-xl font-bold text-imperial-text dark:text-imperial-text-dark">Activity Dashboard</h2>
      <p className="mt-1 text-sm text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Daily goals vs actuals with progress rings.</p>

      {dashboard && (
        <div className="mt-4 rounded-xl border border-imperial-border dark:border-imperial-border-dark bg-imperial-bg-light dark:bg-imperial-bg-dark p-4">
          <h3 className="m-0 text-lg font-bold text-imperial-text dark:text-imperial-text-dark">Sales Dashboard</h3>
          <p className="mt-1 text-sm text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Portfolio KPIs and momentum toward $100k YTD target.</p>

          <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
            <div className="rounded-lg border border-imperial-border dark:border-imperial-border-dark bg-imperial-surface dark:bg-imperial-surface-dark p-3">
              <p className="text-xs uppercase tracking-wide text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Conversion Rate</p>
              <p className="mt-1 text-2xl font-bold text-imperial-text dark:text-imperial-text-dark">{dashboard.conversion_rate.toFixed(1)}%</p>
            </div>
            <div className="rounded-lg border border-imperial-border dark:border-imperial-border-dark bg-imperial-surface dark:bg-imperial-surface-dark p-3">
              <p className="text-xs uppercase tracking-wide text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Avg Profit</p>
              <p className="mt-1 text-2xl font-bold text-imperial-text dark:text-imperial-text-dark">${Math.round(dashboard.avg_profit).toLocaleString()}</p>
            </div>
            <div className="rounded-lg border border-imperial-border dark:border-imperial-border-dark bg-imperial-surface dark:bg-imperial-surface-dark p-3">
              <p className="text-xs uppercase tracking-wide text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Month Sold</p>
              <p className="mt-1 text-2xl font-bold text-imperial-text dark:text-imperial-text-dark">{dashboard.month_sold}</p>
            </div>
            <div className="rounded-lg border border-imperial-border dark:border-imperial-border-dark bg-imperial-surface dark:bg-imperial-surface-dark p-3">
              <p className="text-xs uppercase tracking-wide text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Pending Videos</p>
              <p className="mt-1 text-2xl font-bold text-imperial-text dark:text-imperial-text-dark">{dashboard.pending_video_approvals}</p>
            </div>
          </div>

          <div className="mt-4 rounded-lg border border-imperial-success bg-imperial-success/10 p-3">
            <div className="flex items-center justify-between text-sm font-semibold text-imperial-success">
              <span>$100k YTD Progress</span>
              <span>{dashboard.ytd_progress_percent.toFixed(1)}%</span>
            </div>
            <div className="mt-2 h-3 rounded-full bg-imperial-success/20">
              <div className={`h-3 rounded-full bg-imperial-success ${ytdWidth}`} />
            </div>
            <p className="mt-2 text-xs text-imperial-success">${Math.round(dashboard.ytd_sales).toLocaleString()} / ${Math.round(dashboard.ytd_target).toLocaleString()}</p>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-imperial-border dark:border-imperial-border-dark bg-imperial-surface dark:bg-imperial-surface-dark p-3">
              <p className="text-xs uppercase tracking-wide text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Best-Selling Brands</p>
              <div className="mt-2 space-y-2">
                {dashboard.best_selling_brands.map((row) => {
                  const maxCount = Math.max(...dashboard.best_selling_brands.map((x) => x.count), 1)
                  const pct = (row.count / maxCount) * 100
                  const widthClass = barWidthClass(pct)
                  return (
                    <div key={row.brand}>
                      <div className="mb-1 flex items-center justify-between text-xs font-semibold text-imperial-text dark:text-imperial-text-dark">
                        <span>{row.brand}</span>
                        <span>{row.count}</span>
                      </div>
                      <div className="h-2 rounded-full bg-imperial-bg-light dark:bg-imperial-bg-dark">
                        <div className={`h-2 rounded-full bg-imperial-primary ${widthClass}`} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="rounded-lg border border-imperial-gold bg-imperial-gold/10 p-3">
              <p className="text-xs uppercase tracking-wide text-imperial-gold">Deal of the Day</p>
              {dashboard.deal_of_the_day ? (
                <>
                  <p className="mt-2 text-base font-bold text-imperial-gold">
                    {dashboard.deal_of_the_day.year} {dashboard.deal_of_the_day.make} {dashboard.deal_of_the_day.model}
                  </p>
                  <p className="text-sm text-imperial-gold">MSRP: ${Math.round(dashboard.deal_of_the_day.msrp || 0).toLocaleString()}</p>
                  <p className="text-sm text-imperial-gold">Reliability: {dashboard.deal_of_the_day.reliability_score ?? "n/a"}</p>
                </>
              ) : (
                <p className="mt-2 text-sm text-imperial-gold">No spotlight deal available.</p>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
        <input type="number" min={1} value={salespersonId} onChange={(e) => setSalespersonId(Math.max(1, Number(e.target.value || 1)))} aria-label="Salesperson id" placeholder="salesperson id" className="rounded-lg border border-imperial-border dark:border-imperial-border-dark px-3 py-2 text-sm md:col-span-1 bg-imperial-bg-light dark:bg-imperial-bg-dark text-imperial-text dark:text-imperial-text-dark" />
        <input type="number" value={goalForm.calls} onChange={(e) => setGoalForm((p) => ({ ...p, calls: Number(e.target.value) }))} aria-label="Calls goal" placeholder="Calls" className="rounded-lg border border-imperial-border dark:border-imperial-border-dark px-3 py-2 text-sm bg-imperial-bg-light dark:bg-imperial-bg-dark text-imperial-text dark:text-imperial-text-dark" />
        <input type="number" value={goalForm.texts} onChange={(e) => setGoalForm((p) => ({ ...p, texts: Number(e.target.value) }))} aria-label="Texts goal" placeholder="Texts" className="rounded-lg border border-imperial-border dark:border-imperial-border-dark px-3 py-2 text-sm bg-imperial-bg-light dark:bg-imperial-bg-dark text-imperial-text dark:text-imperial-text-dark" />
        <input type="number" value={goalForm.emails} onChange={(e) => setGoalForm((p) => ({ ...p, emails: Number(e.target.value) }))} aria-label="Emails goal" placeholder="Emails" className="rounded-lg border border-imperial-border dark:border-imperial-border-dark px-3 py-2 text-sm bg-imperial-bg-light dark:bg-imperial-bg-dark text-imperial-text dark:text-imperial-text-dark" />
        <input type="number" value={goalForm.appointments} onChange={(e) => setGoalForm((p) => ({ ...p, appointments: Number(e.target.value) }))} aria-label="Appointments goal" placeholder="Appointments" className="rounded-lg border border-imperial-border dark:border-imperial-border-dark px-3 py-2 text-sm bg-imperial-bg-light dark:bg-imperial-bg-dark text-imperial-text dark:text-imperial-text-dark" />
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button type="button" onClick={saveGoals} className="rounded-lg bg-imperial-gold px-4 py-2 text-sm font-semibold text-imperial-primary hover:bg-imperial-primary-light hover:text-white focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2">Save Today's Goals</button>
        <button type="button" onClick={() => void load()} className="rounded-lg border border-imperial-border dark:border-imperial-border-dark px-4 py-2 text-sm font-semibold text-imperial-primary dark:text-imperial-primary-light hover:bg-imperial-bg-light dark:hover:bg-imperial-bg-dark focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2">Refresh</button>
      </div>
      {status && <p className="mt-2 text-sm font-semibold text-imperial-success">{status}</p>}
      {error && <p className="mt-2 text-sm font-semibold text-imperial-danger">{error}</p>}

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-4">
        {activity && [
          { key: "calls", label: "Calls", actual: activity.actual.calls, goal: activity.goals.calls, pct: activity.progress_percent.calls },
          { key: "texts", label: "Texts", actual: activity.actual.texts, goal: activity.goals.texts, pct: activity.progress_percent.texts },
          { key: "emails", label: "Emails", actual: activity.actual.emails, goal: activity.goals.emails, pct: activity.progress_percent.emails },
          { key: "appointments", label: "Appointments", actual: activity.actual.appointments, goal: activity.goals.appointments, pct: activity.progress_percent.appointments },
        ].map((item) => {
          const ringClass =
            item.pct >= 100
              ? "progress-ring-fill-100"
              : item.pct >= 75
                ? "progress-ring-fill-75"
                : item.pct >= 50
                  ? "progress-ring-fill-50"
                  : item.pct >= 25
                    ? "progress-ring-fill-25"
                    : "progress-ring-fill-0"
          return (
            <div key={item.key} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">{item.label}</p>
              <div className={`mx-auto mt-2 flex h-20 w-20 items-center justify-center rounded-full ${ringClass}`}>
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-white text-xs font-bold text-slate-700">
                  {Math.round(item.pct)}%
                </div>
              </div>
              <p className="mt-2 text-center text-sm font-semibold text-slate-900">{item.actual} / {item.goal || 0}</p>
            </div>
          )
        })}
      </div>
    </section>
  )
}
