import { useEffect, useRef, useState } from "react";

type ValueComparisonGaugeProps = {
  kbbValue?: number;
  msrp?: number;
  ourPrice?: number;
  currency?: string;
};

// Props: kbbValue, msrp, ourPrice, currency (default $)
export default function ValueComparisonGauge({ kbbValue, msrp, ourPrice, currency = "$" }: ValueComparisonGaugeProps) {
  // Calculate anchors
  const anchor = kbbValue || msrp;
  const savings = Math.max(0, (anchor ?? 0) - (ourPrice ?? 0));
  const [displaySavings, setDisplaySavings] = useState(0);
  const [markerPos, setMarkerPos] = useState(100); // percent from left (100 = right)
  const gaugeRef = useRef<HTMLDivElement>(null);

  // Animate savings count up
  useEffect(() => {
    let start = 0;
    let raf: number;
    const duration = 1000;
    const animate = (ts: number) => {
      if (!start) start = ts;
      const progress = Math.min(1, (ts - start) / duration);
      setDisplaySavings(Math.round(savings * progress));
      if (progress < 1) raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [savings]);

  // Animate marker slide in
  useEffect(() => {
    let raf: number;
    let start: number;
    const duration = 1000;
    const startPos = 100;
    const endPos = anchor && ourPrice ? Math.max(0, Math.min(100, ((ourPrice - (msrp ?? anchor)) / (anchor - (msrp ?? anchor))) * 100)) : 0;
    const animate = (ts: number) => {
      if (!start) start = ts;
      const progress = Math.min(1, (ts - start) / duration);
      setMarkerPos(startPos + (endPos - startPos) * progress);
      if (progress < 1) raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [anchor, ourPrice, msrp]);

  // Gauge width
  const gaugeWidth = 240;
  // Marker position (px)
  const markerPx = (markerPos / 100) * gaugeWidth;

  return (
    <div className="w-full flex flex-col items-center gap-2">
      <div className="relative w-full max-w-[260px] h-12 flex items-center">
        {/* Gauge bar */}
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-full h-4 rounded-full bg-imperial-border dark:bg-imperial-border-dark" style={{ width: gaugeWidth }} />
        {/* Market Value anchor */}
        <div className="absolute left-0 top-0 flex flex-col items-center" style={{ left: 0 }}>
          <span className="text-xs font-semibold text-imperial-text-secondary dark:text-imperial-text-secondary-dark">Market Value</span>
          <span className="text-xs text-imperial-text-secondary dark:text-imperial-text-secondary-dark">{currency}{kbbValue?.toLocaleString() || msrp?.toLocaleString() || "-"}</span>
        </div>
        {/* Our Price marker */}
        <div
          className="absolute top-1/2 -translate-y-1/2 flex flex-col items-center transition-transform duration-700"
          style={{ left: markerPx, zIndex: 2 }}
        >
          <div className="w-0 h-0 border-l-8 border-r-8 border-b-8 border-l-transparent border-r-transparent border-b-imperial-gold" />
          <span className="mt-1 text-xs font-bold text-imperial-gold">Our Price</span>
          <span className="text-xs text-imperial-primary dark:text-imperial-primary-light">{currency}{ourPrice?.toLocaleString() || "-"}</span>
        </div>
      </div>
      {/* Savings */}
      <div className="mt-2 flex flex-col items-center">
        <span className="text-3xl font-extrabold text-imperial-gold" style={{ lineHeight: 1 }}>{currency}{displaySavings.toLocaleString()}</span>
        <span className="text-xs font-semibold text-imperial-text-secondary dark:text-imperial-text-secondary-dark">YOU SAVE vs. Market</span>
      </div>
    </div>
  );
}
