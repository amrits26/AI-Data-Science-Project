import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import ActivityDashboard from "./ActivityDashboard"
import LifecycleAgents from "./LifecycleAgents"

const mockApi = vi.hoisted(() => ({
  getLeadsSummary: vi.fn(),
  getLeadContacts: vi.fn(),
  logLeadContact: vi.fn(),
  scoreLead: vi.fn(),
  getDailyGoals: vi.fn(),
  getActivityToday: vi.fn(),
  getDashboardMe: vi.fn(),
  setDailyGoals: vi.fn(),
}))

vi.mock("../services/api", () => ({
  api: mockApi,
}))

describe("Phase 3 Salesperson Tools", () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.getLeadsSummary.mockResolvedValue([
      { customer_id: 7, name: "Avery Lead", contact_count: 2, score: 82, tier: "hot" },
    ])
    mockApi.getLeadContacts.mockResolvedValue([
      { id: 1, contact_type: "call", outcome: "connected" },
      { id: 2, contact_type: "text", outcome: "completed" },
    ])
    mockApi.logLeadContact.mockResolvedValue({ status: "ok" })
    mockApi.scoreLead.mockResolvedValue({ status: "ok", customer_id: 7, score: 90, tier: "hot", components: { recency: 1, contact_count: 0.4, chat_engagement: 0.8, budget_match: 0.8 } })

    mockApi.getDailyGoals.mockResolvedValue({
      status: "ok",
      salesperson_id: "default-sales",
      goal_date: "2026-01-01",
      goals: { calls: 10, texts: 12, emails: 8, appointments: 3 },
    })
    mockApi.getActivityToday.mockResolvedValue({
      status: "ok",
      salesperson_id: "default-sales",
      date: "2026-01-01",
      actual: { calls: 4, texts: 5, emails: 3, appointments: 1 },
      goals: { calls: 10, texts: 12, emails: 8, appointments: 3 },
      progress_percent: { calls: 40, texts: 41.7, emails: 37.5, appointments: 33.3 },
    })
    mockApi.setDailyGoals.mockResolvedValue({ status: "ok" })
    mockApi.getDashboardMe.mockResolvedValue({
      status: "ok",
      conversion_rate: 22.5,
      avg_profit: 3500,
      month_sold: 4,
      ytd_sales: 42000,
      ytd_target: 100000,
      ytd_progress_percent: 42,
      best_selling_brands: [{ brand: "Toyota", count: 5 }],
      deal_of_the_day: { id: 1, year: 2022, make: "Toyota", model: "Camry", msrp: 30000, reliability_score: 82 },
      pending_video_approvals: 1,
    })
  })

  it("renders lifecycle lead badge and logs a contact", async () => {
    render(<LifecycleAgents />)

    expect(await screen.findByText(/Avery Lead/i)).toBeInTheDocument()
    expect(await screen.findByText(/^hot$/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: /Log Call/i }))

    await waitFor(() => expect(mockApi.logLeadContact).toHaveBeenCalledTimes(1))
    expect(mockApi.scoreLead).toHaveBeenCalledWith(7, { auto_schedule: true })
  })

  it("loads activity data and saves goals", async () => {
    render(<ActivityDashboard />)

    expect(await screen.findByText(/Activity Dashboard/i)).toBeInTheDocument()
    expect(await screen.findByText("4 / 10")).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: /Save Today's Goals/i }))

    await waitFor(() => expect(mockApi.setDailyGoals).toHaveBeenCalledTimes(1))
  })
})
