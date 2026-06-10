import { useEffect, useMemo, useState } from "react"

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts"

import { api } from "../services/api"
import type { CarDetail, FinanceEstimateResult, PublicInventoryCar, TradeInEstimateResult } from "../types"

const MIN_PRICE = 12000
const MAX_PRICE = 80000
const MIN_TERM = 24
const MAX_TERM = 84
const BREAK_EVEN_MONTH = 48

function termPositionClass(termMonths: number): string {
  switch (termMonths) {
    case 24:
      return "term-pos-24"
    case 36:
      return "term-pos-36"
    case 48:
      return "term-pos-48"
    case 60:
      return "term-pos-60"
    case 72:
      return "term-pos-72"
    case 84:
      return "term-pos-84"
    default:
      return "term-pos-60"
  }
}

function savingsWidthClass(percent: number): string {
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

function calculateMonthlyPayment(price: number, down: number, annualRate: number, termMonths: number): number {
  const principal = Math.max(price - down, 0)
  const monthlyRate = annualRate / 12 / 100
  if (!principal || !termMonths) return 0
  if (monthlyRate === 0) return principal / termMonths
  const factor = Math.pow(1 + monthlyRate, termMonths)
  return (principal * monthlyRate * factor) / (factor - 1)
}

export default function FinancialTools() {
  const [price, setPrice] = useState(32000)
  const [down, setDown] = useState(4500)
  const [apr, setApr] = useState(6.5)
  const [term, setTerm] = useState(60)

  const [estimate, setEstimate] = useState<FinanceEstimateResult | null>(null)
  const [estimateLoading, setEstimateLoading] = useState(false)
  const [estimateError, setEstimateError] = useState("")

  const [tradeStep, setTradeStep] = useState<1 | 2 | 3>(1)
  const [tradeYear, setTradeYear] = useState<number>(2020)
  const [tradeMake, setTradeMake] = useState("Toyota")
  const [tradeModel, setTradeModel] = useState("Camry")
  const [tradeCondition, setTradeCondition] = useState("good")
  const [tradeMileage, setTradeMileage] = useState(42000)
  const [tradeEstimate, setTradeEstimate] = useState<TradeInEstimateResult | null>(null)
  const [tradeLeadName, setTradeLeadName] = useState("")
  const [tradeLeadPhone, setTradeLeadPhone] = useState("")
  const [tradeLeadEmail, setTradeLeadEmail] = useState("")
  const [tradeStatus, setTradeStatus] = useState("")

  const [inventoryOptions, setInventoryOptions] = useState<PublicInventoryCar[]>([])
  const [compareIds, setCompareIds] = useState<number[]>([])
  const [compareCars, setCompareCars] = useState<CarDetail[]>([])

  const [showResumeModal, setShowResumeModal] = useState(false)
  const [resumeName, setResumeName] = useState("")
  const [resumeEmail, setResumeEmail] = useState("")
  const [resumePhone, setResumePhone] = useState("")
  const [resumeStatus, setResumeStatus] = useState("")
  const [walkAwayMode, setWalkAwayMode] = useState(false)

  const msrp = useMemo(() => estimate?.msrp ?? Math.round(price * 1.12), [estimate, price])
  const savings = useMemo(() => estimate?.savings ?? Math.max(msrp - price, 0), [estimate, msrp, price])
  const savingsPercent = useMemo(() => estimate?.savings_percent ?? (msrp > 0 ? (savings / msrp) * 100 : 0), [estimate, msrp, savings])
  const financed = useMemo(() => estimate?.financed_amount ?? Math.max(price - down, 0), [estimate, price, down])
  const monthlyPayment = useMemo(() => estimate?.monthly_payment ?? calculateMonthlyPayment(price, down, apr, term), [estimate, price, down, apr, term])
  const totalCost = useMemo(() => estimate?.total_cost ?? (monthlyPayment * term + down), [estimate, monthlyPayment, term, down])
  const selectedTermClass = useMemo(() => termPositionClass(term), [term])
  const savingsBarClass = useMemo(() => savingsWidthClass(savingsPercent), [savingsPercent])
  const breakEvenMonth = useMemo(() => estimate?.break_even_month ?? BREAK_EVEN_MONTH, [estimate])
  const clampedDown = useMemo(() => Math.min(Math.max(down, 0), price), [down, price])

  useEffect(() => {
    const timeout = setTimeout(async () => {
      setEstimateLoading(true)
      setEstimateError("")
      try {
        const result = await api.financeEstimate({
          price,
          down_payment: clampedDown,
          annual_rate: apr,
          term_months: term,
          msrp: Math.round(price * 1.12),
        })
        setEstimate(result)
      } catch (err: any) {
        setEstimate(null)
        setEstimateError(err?.message || "Unable to estimate payment")
      } finally {
        setEstimateLoading(false)
      }
    }, 220)

    return () => clearTimeout(timeout)
  }, [price, clampedDown, apr, term])

  useEffect(() => {
    const loadInventoryOptions = async () => {
      try {
        const page = await api.listPublicInventory({ page: 1, page_size: 24 })
        setInventoryOptions(page.items)
      } catch {
        setInventoryOptions([])
      }
    }
    void loadInventoryOptions()
  }, [])

  useEffect(() => {
    const loadCars = async () => {
      if (!compareIds.length) {
        setCompareCars([])
        return
      }
      try {
        const cars = await Promise.all(compareIds.map((id) => api.getCar(id)))
        setCompareCars(cars)
      } catch {
        setCompareCars([])
      }
    }
    void loadCars()
  }, [compareIds])

  const toggleCompareCar = (carId: number) => {
    setCompareIds((prev) => {
      if (prev.includes(carId)) {
        return prev.filter((id) => id !== carId)
      }
      if (prev.length >= 3) {
        return prev
      }
      return [...prev, carId]
    })
  }

  const radarPayload = useMemo(() => {
    if (compareCars.length < 2) {
      return { data: [], winner: "" }
    }

    const getRange = (values: number[]) => {
      const min = Math.min(...values)
      const max = Math.max(...values)
      return { min, max }
    }
    const normalize = (value: number, min: number, max: number, invert = false) => {
      if (max <= min) return 60
      const ratio = (value - min) / (max - min)
      const score = invert ? (1 - ratio) * 100 : ratio * 100
      return Math.max(0, Math.min(100, score))
    }

    const priceValues = compareCars.map((c) => Number(c.msrp || c.used_avg_price || 0))
    const mpgValues = compareCars.map((c) => Number(c.mpg_highway || 0))
    const hpValues = compareCars.map((c) => Number(c.horsepower || 0))
    const safetyValues = compareCars.map((c) => Number(c.safety_rating || 0))
    const reliabilityValues = compareCars.map((c) => Number(c.reliability_score || 0))
    const torqueValues = compareCars.map((c) => Number(c.torque || 0))

    const priceRange = getRange(priceValues)
    const mpgRange = getRange(mpgValues)
    const hpRange = getRange(hpValues)
    const safetyRange = getRange(safetyValues)
    const reliabilityRange = getRange(reliabilityValues)
    const torqueRange = getRange(torqueValues)

    const labels = compareCars.map((c) => `${c.year} ${c.make} ${c.model}`)
    const data = [
      { axis: "Price", values: compareCars.map((c) => normalize(Number(c.msrp || c.used_avg_price || 0), priceRange.min, priceRange.max, true)) },
      { axis: "MPG", values: compareCars.map((c) => normalize(Number(c.mpg_highway || 0), mpgRange.min, mpgRange.max)) },
      { axis: "HP", values: compareCars.map((c) => normalize(Number(c.horsepower || 0), hpRange.min, hpRange.max)) },
      { axis: "Safety", values: compareCars.map((c) => normalize(Number(c.safety_rating || 0), safetyRange.min, safetyRange.max)) },
      { axis: "Reliability", values: compareCars.map((c) => normalize(Number(c.reliability_score || 0), reliabilityRange.min, reliabilityRange.max)) },
      { axis: "Torque", values: compareCars.map((c) => normalize(Number(c.torque || 0), torqueRange.min, torqueRange.max)) },
    ].map((row) => {
      const shaped: Record<string, any> = { axis: row.axis }
      row.values.forEach((score, idx) => {
        shaped[labels[idx]] = Number(score.toFixed(1))
      })
      return shaped
    })

    const totals = labels.map((label) =>
      data.reduce((sum, row) => sum + Number(row[label] || 0), 0)
    )
    const winnerIndex = totals.indexOf(Math.max(...totals))
    return { data, winner: labels[winnerIndex] }
  }, [compareCars])

  const runTradeStepOne = async () => {
    setTradeStatus("")
    try {
      const result = await api.tradeInEstimate({
        year: tradeYear,
        make: tradeMake,
        model: tradeModel,
        mileage: 30000,
        condition: "good",
      })
      setTradeEstimate(result)
      setTradeStep(2)
    } catch (err: any) {
      setTradeStatus(err?.message || "Unable to fetch estimate")
    }
  }

  const runTradeStepTwo = async () => {
    setTradeStatus("")
    try {
      const result = await api.tradeInEstimate({
        year: tradeYear,
        make: tradeMake,
        model: tradeModel,
        mileage: tradeMileage,
        condition: tradeCondition,
      })
      setTradeEstimate(result)
      setTradeStep(3)
    } catch (err: any) {
      setTradeStatus(err?.message || "Unable to refine estimate")
    }
  }

  const submitTradeLead = async () => {
    setTradeStatus("")
    try {
      const resume = await api.resumeDeal({
        name: tradeLeadName || "Trade-In Shopper",
        phone: tradeLeadPhone,
        email: tradeLeadEmail,
        payment_estimate: monthlyPayment,
        trade_in_estimate: tradeEstimate?.estimate_mid,
        snapshot: {
          payment: { price, down, apr, term },
          trade_in: {
            year: tradeYear,
            make: tradeMake,
            model: tradeModel,
            condition: tradeCondition,
            mileage: tradeMileage,
          },
        },
      })
      setTradeStatus(`Lead saved. Resume link sent${resume.sms?.status === "sent" ? " via SMS" : ""}.`)
    } catch (err: any) {
      setTradeStatus(err?.message || "Unable to save lead")
    }
  }

  const saveAndExit = async () => {
    setResumeStatus("")
    try {
      const resume = await api.resumeDeal({
        name: resumeName || "Payment Estimator Shopper",
        email: resumeEmail,
        phone: resumePhone,
        payment_estimate: monthlyPayment,
        trade_in_estimate: tradeEstimate?.estimate_mid,
        car_id: compareIds[0],
        walkaway: walkAwayMode,
        source: walkAwayMode ? "payment-estimator" : "resume",
        snapshot: {
          payment: { price, down, apr, term },
          compare_ids: compareIds,
        },
      })
      setResumeStatus(`${walkAwayMode ? "Walk-away saved" : "Saved"}. Resume at ${resume.resume_link}`)
    } catch (err: any) {
      setResumeStatus(err?.message || "Unable to save deal")
    }
  }

  return (
    <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="m-0 text-xl font-bold text-slate-900">Payment Estimator</h2>
        <p className="mt-1 text-sm text-slate-600">Dial in the numbers with sliders to see an instant monthly estimate.</p>

        <div className="mt-4 space-y-4">
          <label className="block">
            <div className="mb-1 flex items-center justify-between text-sm font-semibold text-slate-700">
              <span>Vehicle Price</span>
              <span>${price.toLocaleString()}</span>
            </div>
            <input
              type="range"
              min={MIN_PRICE}
              max={MAX_PRICE}
              step={500}
              value={price}
              onChange={(e) => setPrice(Number(e.target.value))}
              aria-label="Vehicle price slider"
              className="h-2 w-full cursor-pointer accent-imperial-primary"
            />
          </label>

          <label className="block">
            <div className="mb-1 flex items-center justify-between text-sm font-semibold text-slate-700">
              <span>Down Payment</span>
              <span>${down.toLocaleString()}</span>
            </div>
            <input
              type="range"
              min={0}
              max={Math.max(price, 1000)}
              step={250}
              value={Math.min(down, price)}
              onChange={(e) => setDown(Number(e.target.value))}
              aria-label="Down payment slider"
              className="h-2 w-full cursor-pointer accent-imperial-primary"
            />
          </label>

          <label className="block">
            <div className="mb-1 flex items-center justify-between text-sm font-semibold text-slate-700">
              <span>Interest Rate (APR)</span>
              <span>{apr.toFixed(1)}%</span>
            </div>
            <input
              type="range"
              min={1}
              max={14}
              step={0.1}
              value={apr}
              onChange={(e) => setApr(Number(e.target.value))}
              aria-label="APR slider"
              className="h-2 w-full cursor-pointer accent-imperial-primary"
            />
          </label>

          <label className="block">
            <div className="mb-1 flex items-center justify-between text-sm font-semibold text-slate-700">
              <span>Term</span>
              <span>{term} months</span>
            </div>
            <input
              type="range"
              min={MIN_TERM}
              max={MAX_TERM}
              step={12}
              value={term}
              onChange={(e) => setTerm(Number(e.target.value))}
              aria-label="Loan term slider"
              className="h-2 w-full cursor-pointer accent-imperial-primary"
            />
          </label>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="m-0 text-lg font-bold text-slate-900">Deal Snapshot</h3>

        <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs uppercase tracking-wide text-slate-500">Anchored MSRP</p>
          <p className="mt-1 text-lg font-bold text-slate-500 line-through">${msrp.toLocaleString()}</p>
          <p className="text-3xl font-extrabold text-imperial-primary">${price.toLocaleString()}</p>
        </div>

        <div className="mt-3 rounded-lg border border-green-200 bg-green-50 p-3">
          <div className="flex items-center justify-between text-sm font-semibold text-green-800">
            <span>You save ${savings.toLocaleString()}</span>
            <span>{savingsPercent.toFixed(1)}%</span>
          </div>
          <div className="mt-2 h-2 rounded-full bg-green-100">
            <div
              className={`h-2 rounded-full bg-imperial-accent ${savingsBarClass}`}
              aria-hidden="true"
            />
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="rounded-lg border border-slate-200 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Estimated Monthly</p>
            <p className="mt-1 text-2xl font-extrabold text-slate-900">${monthlyPayment.toFixed(0)}</p>
          </div>
          <div className="rounded-lg border border-slate-200 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Financed Amount</p>
            <p className="mt-1 text-2xl font-extrabold text-slate-900">${financed.toLocaleString()}</p>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-orange-200 bg-orange-50 p-3">
          <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-orange-700">
            <span>Term Timeline</span>
            <span>Total ${totalCost.toFixed(0)}</span>
          </div>
          <div className="relative h-10 rounded-md bg-white">
            <div className="absolute inset-y-1 w-0.5 bg-orange-500 term-pos-48" />
            <div className="absolute left-0 right-0 top-1/2 h-1 -translate-y-1/2 rounded bg-slate-200" />
            <div className={`absolute inset-y-0 w-1 rounded bg-imperial-secondary ${selectedTermClass}`} />
            <p className="absolute -top-4 text-[11px] font-semibold text-orange-700 term-pos-48">
              {breakEvenMonth}-month break-even
            </p>
            <p className={`absolute -bottom-4 text-[11px] font-semibold text-slate-600 ${selectedTermClass}`}>
              Your term: {term}m
            </p>
          </div>
        </div>

        <div className="mt-8 border-t border-slate-200 pt-4">
          <h3 className="m-0 text-base font-bold text-slate-900">Save and Resume Later</h3>
          <p className="mt-1 text-sm text-slate-600">Capture your estimate and get a one-tap resume link.</p>
          <button
            type="button"
            onClick={() => {
              setWalkAwayMode(false)
              setShowResumeModal(true)
            }}
            className="mt-3 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
          >
            Save and Exit
          </button>
          <button
            type="button"
            onClick={() => {
              setWalkAwayMode(true)
              setShowResumeModal(true)
            }}
            className="mt-3 ml-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-800"
          >
            Walk Away + Save Link
          </button>
          {estimateLoading && <p className="mt-2 text-xs text-slate-500">Updating estimate...</p>}
          {estimateError && <p className="mt-2 text-xs text-imperial-danger">{estimateError}</p>}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 lg:col-span-2">
        <h3 className="m-0 text-lg font-bold text-slate-900">Progressive Trade-In Wizard</h3>
        <p className="mt-1 text-sm text-slate-600">Step-by-step estimate that ends with a saved resume link.</p>

        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
          <button type="button" onClick={() => setTradeStep(1)} className={`rounded-lg px-3 py-2 text-sm font-semibold ${tradeStep === 1 ? "bg-imperial-primary text-white" : "bg-slate-100 text-slate-700"}`}>1. Vehicle</button>
          <button type="button" onClick={() => setTradeStep(2)} className={`rounded-lg px-3 py-2 text-sm font-semibold ${tradeStep === 2 ? "bg-imperial-primary text-white" : "bg-slate-100 text-slate-700"}`}>2. Condition</button>
          <button type="button" onClick={() => setTradeStep(3)} className={`rounded-lg px-3 py-2 text-sm font-semibold ${tradeStep === 3 ? "bg-imperial-primary text-white" : "bg-slate-100 text-slate-700"}`}>3. Contact</button>
        </div>

        {tradeStep === 1 && (
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
            <input type="number" value={tradeYear} onChange={(e) => setTradeYear(Number(e.target.value))} aria-label="Trade-in year" placeholder="Year" className="rounded-lg border border-slate-300 px-3 py-2" />
            <input value={tradeMake} onChange={(e) => setTradeMake(e.target.value)} aria-label="Trade-in make" placeholder="Make" className="rounded-lg border border-slate-300 px-3 py-2" />
            <input value={tradeModel} onChange={(e) => setTradeModel(e.target.value)} aria-label="Trade-in model" placeholder="Model" className="rounded-lg border border-slate-300 px-3 py-2" />
            <button type="button" onClick={runTradeStepOne} className="rounded-lg bg-imperial-secondary px-3 py-2 text-sm font-semibold text-white">Get Instant Estimate</button>
          </div>
        )}

        {tradeStep === 2 && (
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
            <select value={tradeCondition} onChange={(e) => setTradeCondition(e.target.value)} aria-label="Trade-in condition" className="rounded-lg border border-slate-300 px-3 py-2">
              <option value="excellent">Excellent</option>
              <option value="good">Good</option>
              <option value="fair">Fair</option>
              <option value="poor">Poor</option>
            </select>
            <input type="number" value={tradeMileage} onChange={(e) => setTradeMileage(Number(e.target.value))} aria-label="Trade-in mileage" placeholder="Mileage" className="rounded-lg border border-slate-300 px-3 py-2" />
            <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm font-semibold text-green-800 md:col-span-1">
              {tradeEstimate ? `$${tradeEstimate.estimate_low.toLocaleString()} - $${tradeEstimate.estimate_high.toLocaleString()}` : "Estimate pending"}
            </div>
            <button type="button" onClick={runTradeStepTwo} className="rounded-lg bg-imperial-secondary px-3 py-2 text-sm font-semibold text-white">Refine Estimate</button>
          </div>
        )}

        {tradeStep === 3 && (
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
            <input value={tradeLeadName} onChange={(e) => setTradeLeadName(e.target.value)} aria-label="Lead name" placeholder="Name" className="rounded-lg border border-slate-300 px-3 py-2" />
            <input value={tradeLeadPhone} onChange={(e) => setTradeLeadPhone(e.target.value)} aria-label="Lead phone" placeholder="Phone" className="rounded-lg border border-slate-300 px-3 py-2" />
            <input value={tradeLeadEmail} onChange={(e) => setTradeLeadEmail(e.target.value)} aria-label="Lead email" placeholder="Email" className="rounded-lg border border-slate-300 px-3 py-2" />
            <button type="button" onClick={submitTradeLead} className="rounded-lg bg-imperial-secondary px-3 py-2 text-sm font-semibold text-white">Save Lead + Send Resume SMS</button>
          </div>
        )}

        {tradeStatus && <p className="mt-3 text-sm font-semibold text-slate-700">{tradeStatus}</p>}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 lg:col-span-2">
        <h3 className="m-0 text-lg font-bold text-slate-900">Comparison Radar</h3>
        <p className="mt-1 text-sm text-slate-600">Select 2 or 3 vehicles to compare price, MPG, HP, safety, reliability, and torque.</p>

        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
          {inventoryOptions.slice(0, 12).map((car) => {
            const checked = compareIds.includes(car.id)
            return (
              <label key={car.id} className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${checked ? "border-imperial-primary bg-red-50" : "border-slate-200 bg-white"}`}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleCompareCar(car.id)}
                  aria-label={`Compare ${car.year} ${car.make} ${car.model}`}
                />
                <span>{car.year} {car.make} {car.model}</span>
              </label>
            )
          })}
        </div>

        <div className="mt-4 h-80">
          {radarPayload.data.length >= 1 ? (
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarPayload.data}>
                <PolarGrid />
                <PolarAngleAxis dataKey="axis" />
                <PolarRadiusAxis domain={[0, 100]} />
                <Tooltip />
                {compareCars.map((car, index) => {
                  const label = `${car.year} ${car.make} ${car.model}`
                  const isWinner = label === radarPayload.winner
                  const palette = ["#B22234", "#1A1A1A", "#0F766E"]
                  return (
                    <Radar
                      key={label}
                      name={label}
                      dataKey={label}
                      stroke={isWinner ? "#22C55E" : palette[index % palette.length]}
                      fill={isWinner ? "rgba(34,197,94,0.2)" : "rgba(178,34,52,0.12)"}
                      fillOpacity={0.9}
                    />
                  )
                })}
              </RadarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-slate-300 text-sm text-slate-500">
              Select at least 2 vehicles to render comparison radar.
            </div>
          )}
        </div>

        {radarPayload.winner && (
          <p className="mt-2 text-sm font-semibold text-green-700">Top overall match: {radarPayload.winner}</p>
        )}
      </div>

      {showResumeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label="Save and resume deal">
          <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-4 shadow-2xl">
            <h3 className="m-0 text-lg font-bold text-slate-900">Save Deal Progress</h3>
            <p className="mt-1 text-sm text-slate-600">{walkAwayMode ? "We will save your walk-away and send a one-tap resume link." : "We will send you a one-tap resume link."}</p>
            <div className="mt-3 grid grid-cols-1 gap-2">
              <input value={resumeName} onChange={(e) => setResumeName(e.target.value)} placeholder="Name" aria-label="Name" className="rounded-lg border border-slate-300 px-3 py-2" />
              <input value={resumePhone} onChange={(e) => setResumePhone(e.target.value)} placeholder="Phone" aria-label="Phone" className="rounded-lg border border-slate-300 px-3 py-2" />
              <input value={resumeEmail} onChange={(e) => setResumeEmail(e.target.value)} placeholder="Email" aria-label="Email" className="rounded-lg border border-slate-300 px-3 py-2" />
            </div>
            {resumeStatus && <p className="mt-2 text-xs font-semibold text-slate-700">{resumeStatus}</p>}
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setShowResumeModal(false)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold">Close</button>
              <button type="button" onClick={saveAndExit} className="rounded-lg bg-imperial-secondary px-3 py-2 text-sm font-semibold text-white">{walkAwayMode ? "Walk Away + Send Link" : "Save + Send Link"}</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
