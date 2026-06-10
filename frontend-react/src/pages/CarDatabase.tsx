import { useEffect, useMemo, useState } from "react"

import { api } from "../services/api"
import type { PublicInventoryCar } from "../types"

type CarDatabaseProps = {
  onAskAI?: (prompt: string) => void
}

function InventorySkeletonCard() {
  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="h-40 animate-pulse bg-slate-200" />
      <div className="space-y-3 p-4">
        <div className="h-4 w-2/3 animate-pulse rounded bg-slate-200" />
        <div className="h-8 w-1/2 animate-pulse rounded bg-slate-200" />
        <div className="h-4 w-3/4 animate-pulse rounded bg-slate-200" />
        <div className="h-9 w-full animate-pulse rounded bg-slate-200" />
      </div>
    </article>
  )
}

export default function CarDatabase({ onAskAI }: CarDatabaseProps) {
  const [rows, setRows] = useState<PublicInventoryCar[]>([])
  const [socialProof, setSocialProof] = useState<Record<number, string>>({})
  const [makeFilter, setMakeFilter] = useState("")
  const [modelFilter, setModelFilter] = useState("")
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    const run = async () => {
      setLoading(true)
      setError("")
      try {
        const response = await api.listPublicInventory({
          page,
          page_size: 12,
          make: makeFilter || undefined,
          model: modelFilter || undefined,
        })
        setRows(response.items)
        setTotal(response.total)
      } catch (e: any) {
        setError(e?.message || "Unable to load cars")
      } finally {
        setLoading(false)
      }
    }
    run()
  }, [page, makeFilter, modelFilter])

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / 12)), [total])

  useEffect(() => {
    const loadSocialProof = async () => {
      if (!rows.length) {
        setSocialProof({})
        return
      }

      const proofs = await Promise.all(
        rows.map(async (car) => {
          try {
            const result = await api.socialProof(car.id)
            return [car.id, result.message] as const
          } catch {
            return [car.id, ""] as const
          }
        })
      )

      const next: Record<number, string> = {}
      proofs.forEach(([id, message]) => {
        if (message) {
          next[id] = message
        }
      })
      setSocialProof(next)
    }

    void loadSocialProof()
  }, [rows])

  const askAboutCar = (car: PublicInventoryCar) => {
    const prompt = `Tell me about this ${car.year} ${car.make} ${car.model} and whether it fits a daily commuter budget.`
    if (onAskAI) {
      onAskAI(prompt)
    }
  }

  return (
    <section aria-label="Vehicle inventory database" className="grid grid-cols-1 gap-4">
      <div className="rounded-xl border border-imperial-border dark:border-imperial-border-dark bg-imperial-surface dark:bg-imperial-surface-dark p-4">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
          <input
            aria-label="Filter by vehicle make"
            className="rounded-lg border border-imperial-border dark:border-imperial-border-dark px-3 py-2 bg-imperial-bg-light dark:bg-imperial-bg-dark text-imperial-text dark:text-imperial-text-dark"
            placeholder="Filter by make"
            value={makeFilter}
            onChange={(e) => {
              setPage(1)
              setMakeFilter(e.target.value)
            }}
          />
          <input
            aria-label="Filter by vehicle model"
            className="rounded-lg border border-imperial-border dark:border-imperial-border-dark px-3 py-2 bg-imperial-bg-light dark:bg-imperial-bg-dark text-imperial-text dark:text-imperial-text-dark"
            placeholder="Filter by model"
            value={modelFilter}
            onChange={(e) => {
              setPage(1)
              setModelFilter(e.target.value)
            }}
          />
          <div role="status" aria-live="polite" className="rounded-lg bg-imperial-bg-light dark:bg-imperial-bg-dark px-3 py-2 text-sm text-imperial-text-secondary dark:text-imperial-text-secondary-dark">
            Showing page {page} of {totalPages} ({total} total vehicles)
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-imperial-border dark:border-imperial-border-dark bg-imperial-surface dark:bg-imperial-surface-dark p-4">
        {loading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, idx) => (
              <InventorySkeletonCard key={idx} />
            ))}
          </div>
        )}
        {error && <p className="text-sm text-imperial-danger">{error}</p>}
        {!loading && !error && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {rows.map((car) => (
              <article key={car.id} className="overflow-hidden rounded-2xl border border-imperial-border dark:border-imperial-border-dark bg-imperial-surface dark:bg-imperial-surface-dark shadow-sm">
                <img
                  src={car.image_url}
                  alt={`${car.year} ${car.make} ${car.model}`}
                  className="h-40 w-full object-cover"
                  loading="lazy"
                />
                <div className="space-y-3 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="m-0 text-base font-bold text-imperial-text dark:text-imperial-text-dark">{car.year} {car.make} {car.model}</h3>
                    {car.stock_count <= 5 && (
                      <span className="rounded-full bg-imperial-gold text-imperial-primary px-2 py-1 text-xs font-semibold">
                        Only {car.stock_count} left
                      </span>
                    )}
                  </div>
                  <p className="text-3xl font-extrabold text-imperial-danger">${(car.msrp || 0).toLocaleString()}</p>
                  <p className="text-sm text-imperial-text-secondary dark:text-imperial-text-secondary-dark">
                    {car.trim || "Standard Trim"} | {car.mileage > 0 ? `${car.mileage.toLocaleString()} mi` : "Mileage on request"}
                  </p>
                  {socialProof[car.id] && (
                    <p className="rounded-md bg-imperial-success/10 px-2 py-1 text-xs font-semibold text-imperial-success">{socialProof[car.id]}</p>
                  )}
                  <button
                    type="button"
                    onClick={() => askAboutCar(car)}
                    className="w-full rounded-lg bg-imperial-primary px-3 py-2 text-sm font-semibold text-white hover:bg-imperial-primary-light focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2"
                  >
                    Ask AI
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 rounded-xl border border-imperial-border dark:border-imperial-border-dark bg-imperial-surface dark:bg-imperial-surface-dark p-4">
        <button
          type="button"
          onClick={() => setPage((prev) => Math.max(1, prev - 1))}
          disabled={page <= 1 || loading}
          className="rounded-lg border border-imperial-border dark:border-imperial-border-dark px-4 py-2 text-sm font-semibold text-imperial-primary dark:text-imperial-primary-light hover:bg-imperial-bg-light dark:hover:bg-imperial-bg-dark disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2"
        >
          Previous
        </button>
        <p className="text-sm text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Page {page} of {totalPages}</p>
        <button
          type="button"
          onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
          disabled={page >= totalPages || loading}
          className="rounded-lg border border-imperial-border dark:border-imperial-border-dark px-4 py-2 text-sm font-semibold text-imperial-primary dark:text-imperial-primary-light hover:bg-imperial-bg-light dark:hover:bg-imperial-bg-dark disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2"
        >
          Next
        </button>
      </div>
    </section>
  )
}
