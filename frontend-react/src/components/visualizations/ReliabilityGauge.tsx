import React from "react";

// Props: score (0-100)
export default function ReliabilityGauge({ score = 0 }) {
  // Color zones
  let color = "text-imperial-danger";
  if (score >= 70) color = "text-imperial-success";
  else if (score >= 40) color = "text-imperial-gold";

  // SVG semicircle gauge
  const radius = 36;
  const circumference = Math.PI * radius;
  const percent = Math.max(0, Math.min(100, score)) / 100;
  const offset = circumference * (1 - percent);

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="90" height="54" viewBox="0 0 90 54">
        <path
          d="M 9 45 A 36 36 0 0 1 81 45"
          fill="none"
          stroke="#e5e7eb"
          strokeWidth="8"
        />
        <path
          d="M 9 45 A 36 36 0 0 1 81 45"
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={color}
          style={{ transition: "stroke-dashoffset 0.7s cubic-bezier(0.4,0,0.2,1)" }}
        />
      </svg>
      <span className={`text-lg font-bold ${color}`}>Reliability: {score}/100</span>
    </div>
  );
}
