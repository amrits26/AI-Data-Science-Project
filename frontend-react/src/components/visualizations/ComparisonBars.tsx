import React from "react";

type ComparisonMetric = {
  key: string;
  label: string;
  leftValue: number;
  rightValue: number;
  leftLabel: string;
  rightLabel: string;
  better: "left" | "right";
  segmentAvg?: number;
  unit?: string;
};

type ComparisonBarsProps = {
  metrics?: ComparisonMetric[];
};

// Props: metrics: [{ key, label, leftValue, rightValue, leftLabel, rightLabel, better, segmentAvg, unit }]
export default function ComparisonBars({ metrics = [] }: ComparisonBarsProps) {
  return (
    <div className="flex flex-col gap-4">
      {metrics.map((m) => (
        <div key={m.key} className="flex flex-col gap-1">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold text-imperial-text dark:text-imperial-text-dark">{m.label}</span>
            <span className="text-xs text-imperial-text-secondary dark:text-imperial-text-secondary-dark">{m.leftLabel} vs. {m.rightLabel}</span>
          </div>
          <div className="relative flex items-center h-7">
            {/* Left bar */}
            <div
              className={`h-4 rounded-l-full ${m.better === "left" ? "bg-imperial-gold" : "bg-imperial-border dark:bg-imperial-border-dark"}`}
              style={{ width: `${m.leftValue}%`, minWidth: 8 }}
            />
            {/* Right bar */}
            <div
              className={`h-4 rounded-r-full ${m.better === "right" ? "bg-imperial-gold" : "bg-imperial-border dark:bg-imperial-border-dark"}`}
              style={{ width: `${m.rightValue}%`, minWidth: 8 }}
            />
            {/* Segment average reference line */}
            {typeof m.segmentAvg === "number" && (
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-imperial-primary/60 border-l-2 border-dashed border-imperial-primary left-1/2"
                style={{ left: `${m.segmentAvg}%` }}
              />
            )}
          </div>
          <div className="flex items-center justify-between mt-1">
            <span className={`text-xs font-bold ${m.better === "left" ? "text-imperial-gold" : "text-imperial-text-secondary dark:text-imperial-text-secondary-dark"}`}>{m.leftLabel}</span>
            <span className={`text-xs font-bold ${m.better === "right" ? "text-imperial-gold" : "text-imperial-text-secondary dark:text-imperial-text-secondary-dark"}`}>{m.rightLabel}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
