import type { VehicleMetadata } from "../types"

type InventoryCardProps = {
  vehicle: VehicleMetadata
  onEstimatePayment?: (vehicle: VehicleMetadata) => void
  onScheduleTestDrive?: (vehicle: VehicleMetadata) => void
  onTalkToSales?: () => void
}

function safeNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A"
  }
  return Number(value).toLocaleString()
}

export default function InventoryCard({
  vehicle,
  onEstimatePayment,
  onScheduleTestDrive,
  onTalkToSales,
}: InventoryCardProps) {
  const title = `${vehicle.year || ""} ${vehicle.make || ""} ${vehicle.model || ""} ${vehicle.trim || ""}`.trim()
  const priceValue = vehicle.price ?? vehicle.msrp ?? vehicle.used_avg_price

  return (
    <article className="rounded-xl border border-imperial-border dark:border-imperial-border-dark bg-imperial-surface dark:bg-imperial-surface-dark p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-bold text-imperial-text dark:text-imperial-text-dark">{title || "Vehicle"}</h4>
          <p className="text-xs text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Stock: {safeNumber(vehicle.stock_count)}</p>
        </div>
        <span className="rounded-full bg-imperial-gold text-imperial-primary px-2 py-1 text-xs font-semibold">
          ${safeNumber(priceValue)}
        </span>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-imperial-text dark:text-imperial-text-dark">
        <div>HP: {safeNumber(vehicle.horsepower)}</div>
        <div>Torque: {safeNumber(vehicle.torque)}</div>
        <div>MPG Hwy: {safeNumber(vehicle.mpg_highway)}</div>
        <div>Towing: {safeNumber(vehicle.towing_capacity)}</div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onEstimatePayment?.(vehicle)}
          className="rounded-md bg-imperial-primary px-2 py-1 text-xs font-semibold text-white hover:bg-imperial-primary-light focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2"
        >
          Estimate Payment
        </button>
        <button
          type="button"
          onClick={() => onScheduleTestDrive?.(vehicle)}
          className="rounded-md border border-imperial-border dark:border-imperial-border-dark px-2 py-1 text-xs font-semibold text-imperial-primary dark:text-imperial-primary-light hover:bg-imperial-bg-light dark:hover:bg-imperial-bg-dark focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2"
        >
          Schedule Test Drive
        </button>
        <button
          type="button"
          onClick={() => onTalkToSales?.()}
          className="rounded-md border border-imperial-gold bg-imperial-gold px-2 py-1 text-xs font-semibold text-imperial-primary hover:bg-imperial-primary-light hover:text-white focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2"
        >
          Talk to Sales
        </button>
      </div>
    </article>
  )
}
