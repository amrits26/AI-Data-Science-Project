import React from "react";

type OwnershipCostChartProps = {
  mpg?: number;
  annualFuelCost?: number;
  fiveYearFuelCost?: number;
  fiveYearMaintCost?: number;
  segmentAvgFuel?: number;
  segmentAvgMaint?: number;
  savings?: number;
  currency?: string;
};

// Props: mpg, annualFuelCost, fiveYearFuelCost, fiveYearMaintCost, segmentAvgFuel, segmentAvgMaint, savings, currency
export default function OwnershipCostChart({ mpg, annualFuelCost, fiveYearFuelCost, fiveYearMaintCost, segmentAvgFuel, segmentAvgMaint, savings, currency = "$" }: OwnershipCostChartProps) {
  // Calculate bar lengths (percent of max)
  const vehicleFuelCost = fiveYearFuelCost ?? 0;
  const vehicleMaintCost = fiveYearMaintCost ?? 0;
  const averageFuelCost = segmentAvgFuel ?? 0;
  const averageMaintCost = segmentAvgMaint ?? 0;
  const maxCost = Math.max(vehicleFuelCost + vehicleMaintCost, averageFuelCost + averageMaintCost, 1);
  const vehiclePct = ((vehicleFuelCost + vehicleMaintCost) / maxCost) * 100;
  const segmentPct = ((averageFuelCost + averageMaintCost) / maxCost) * 100;

  return (
    <div className="flex flex-col gap-3">
      {/* Stacked bar chart */}
      <div className="relative h-8 w-full max-w-[260px] mx-auto flex items-center">
        {/* Vehicle bar */}
        <div className="absolute left-0 top-1/2 -translate-y-1/2 h-4 rounded-full bg-imperial-primary/20 w-full" />
        <div className="absolute left-0 top-1/2 -translate-y-1/2 h-4 rounded-l-full bg-imperial-primary" style={{ width: `${vehiclePct}%`, zIndex: 2 }} />
        {/* Segment average bar (dashed) */}
        <div className="absolute left-0 top-1/2 -translate-y-1/2 h-4 border-2 border-dashed border-imperial-gold w-full opacity-40 pointer-events-none" style={{ width: `${segmentPct}%`, zIndex: 1 }} />
      </div>
      {/* Key numbers */}
      <div className="flex flex-col items-center gap-1 mt-2">
        <span className="text-2xl font-extrabold text-imperial-primary dark:text-imperial-primary-light">{mpg} MPG</span>
        <span className="text-xs text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Annual Fuel Cost: {currency}{annualFuelCost?.toLocaleString()}</span>
        <span className="text-xs text-imperial-success font-semibold">You save {currency}{savings?.toLocaleString()} over 5 years</span>
      </div>
    </div>
  );
}
