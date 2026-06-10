import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import FinancialTools from "./FinancialTools"

const mockApi = vi.hoisted(() => ({
  financeEstimate: vi.fn(),
  listPublicInventory: vi.fn(),
  getCar: vi.fn(),
  tradeInEstimate: vi.fn(),
  resumeDeal: vi.fn(),
}))

vi.mock("../services/api", () => ({
  api: mockApi,
}))

vi.mock("recharts", () => {
  const Mock = ({ children }: any) => <div>{children}</div>
  return {
    ResponsiveContainer: Mock,
    RadarChart: Mock,
    PolarGrid: Mock,
    PolarAngleAxis: Mock,
    PolarRadiusAxis: Mock,
    Tooltip: Mock,
    Radar: ({ name }: { name: string }) => <div>{name}</div>,
  }
})

describe("FinancialTools Phase 2", () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.financeEstimate.mockResolvedValue({
      price: 32000,
      msrp: 36000,
      financed_amount: 27500,
      monthly_payment: 611.22,
      total_cost: 41173.2,
      savings: 4000,
      savings_percent: 11.11,
      break_even_month: 48,
    })
    mockApi.listPublicInventory.mockResolvedValue({
      page: 1,
      page_size: 12,
      total: 3,
      items: [
        { id: 1, year: 2022, make: "Toyota", model: "Camry", msrp: 30000, mileage: 22000, stock_count: 4, image_url: "x" },
        { id: 2, year: 2022, make: "Honda", model: "Accord", msrp: 31000, mileage: 21000, stock_count: 4, image_url: "x" },
      ],
    })
    mockApi.getCar.mockImplementation(async (id: number) => {
      if (id === 1) {
        return {
          id: 1,
          year: 2022,
          make: "Toyota",
          model: "Camry",
          msrp: 30000,
          mpg_highway: 39,
          horsepower: 203,
          safety_rating: 5,
          reliability_score: 82,
          torque: 184,
        }
      }
      return {
        id: 2,
        year: 2022,
        make: "Honda",
        model: "Accord",
        msrp: 31000,
        mpg_highway: 38,
        horsepower: 192,
        safety_rating: 5,
        reliability_score: 79,
        torque: 192,
      }
    })
    mockApi.tradeInEstimate.mockResolvedValue({
      make: "Toyota",
      model: "Camry",
      year: 2020,
      mileage: 42000,
      condition: "good",
      baseline_price: 20000,
      estimate_low: 18000,
      estimate_high: 20000,
      estimate_mid: 19000,
      source: "cars.used_avg_price",
    })
    mockApi.resumeDeal.mockResolvedValue({
      status: "ok",
      customer_id: 10,
      resume_token: "token-123",
      resume_link: "http://localhost:3000/resume/token-123",
      sms: { status: "sent" },
    })
  })

  it("renders trade-in wizard flow and sends resume lead", async () => {
    render(<FinancialTools />)

    await waitFor(() => expect(mockApi.tradeInEstimate).not.toHaveBeenCalled())

    const estimateBtn = await screen.findByRole("button", { name: /Get Instant Estimate/i })
    await userEvent.click(estimateBtn)
    expect(mockApi.tradeInEstimate).toHaveBeenCalledTimes(1)

    const refineBtn = await screen.findByRole("button", { name: /Refine Estimate/i })
    await userEvent.click(refineBtn)
    expect(mockApi.tradeInEstimate).toHaveBeenCalledTimes(2)

    const saveLeadBtn = await screen.findByRole("button", { name: /Save Lead \+ Send Resume SMS/i })
    await userEvent.type(screen.getByLabelText("Lead name"), "Alex Lead")
    await userEvent.type(screen.getByLabelText("Lead phone"), "5551234567")
    await userEvent.click(saveLeadBtn)

    await waitFor(() => expect(mockApi.resumeDeal).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(/Lead saved\. Resume link sent/i)).toBeInTheDocument()
  })

  it("renders comparison radar winner when 2 cars are selected", async () => {
    render(<FinancialTools />)

    const checkboxes = await screen.findAllByRole("checkbox")
    await userEvent.click(checkboxes[0])
    await userEvent.click(checkboxes[1])

    await waitFor(() => expect(mockApi.getCar.mock.calls.length).toBeGreaterThanOrEqual(2))
    expect(await screen.findByText(/Top overall match:/i)).toBeInTheDocument()
  })

  it("opens save-and-exit modal and submits resume-deal", async () => {
    render(<FinancialTools />)

    const openButtons = await screen.findAllByRole("button", { name: /Save and Exit/i })
    const openBtn = openButtons[0]
    await userEvent.click(openBtn)

    await userEvent.type(screen.getByLabelText("Name"), "Morgan")
    await userEvent.type(screen.getByLabelText("Phone"), "5551239999")
    await userEvent.click(screen.getByRole("button", { name: /Save \+ Send Link/i }))

    await waitFor(() => expect(mockApi.resumeDeal).toHaveBeenCalled())
    expect(await screen.findByText(/Saved\. Resume at/i)).toBeInTheDocument()
  })
})
