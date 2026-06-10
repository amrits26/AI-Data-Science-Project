import { useState, useEffect, type ReactNode } from "react";
import ValueComparisonGauge from "./ValueComparisonGauge";
import ComparisonBars from "./ComparisonBars";
import OwnershipCostChart from "./OwnershipCostChart";
import TrendingNow from "./TrendingNow";
import VehicleActivity from "./VehicleActivity";
import SafetyStars from "./SafetyStars";
import ReliabilityGauge from "./ReliabilityGauge";
import WillItFitVisualization from "./WillItFitVisualization";
import { fetchVisualizations } from "../../services/visualizations";

type VisualizationsResponse = {
  vehicle?: Record<string, any>;
  comparison?: Record<string, any> | null;
  trending?: Array<Record<string, any>>;
  activity?: Record<string, any> | null;
  safety?: Record<string, any> | null;
  reliability?: Record<string, any> | null;
  fit?: Record<string, any> | null;
};

type VisualizationsPanelProps = {
  stockNumber?: string | null;
};


// Accepts stockNumber as prop (required)
export default function VisualizationsPanel({ stockNumber }: VisualizationsPanelProps) {
  // Collapsible state for each section
  const [open, setOpen] = useState({
    value: true,
    compare: true,
    ownership: true,
    social: true,
    safety: true,
    fit: true,
  });
  const [data, setData] = useState<VisualizationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!stockNumber) return;
    setLoading(true);
    setError(null);
    fetchVisualizations(stockNumber)
      .then((res) => setData(res))
      .catch((e) => setError("Failed to load visualizations."))
      .finally(() => setLoading(false));
  }, [stockNumber]);

  if (!stockNumber) {
    return <div className="p-4 text-imperial-text-secondary">No vehicle selected.</div>;
  }
  if (loading) {
    return <div className="p-4 animate-pulse text-imperial-text-secondary">Loading visualizations…</div>;
  }
  if (error) {
    return <div className="p-4 text-imperial-danger">{error}</div>;
  }
  if (!data) {
    return <div className="p-4 text-imperial-text-secondary">No data available.</div>;
  }

  // Map backend data to props for each visualization
  const { vehicle, comparison, trending, activity, safety, reliability, fit } = data;

  return (
    <div className="flex flex-col gap-4 h-full overflow-y-auto p-4 bg-imperial-surface dark:bg-imperial-surface-dark">
      {/* Value at a Glance */}
      <CollapsibleCard
        title="Value at a Glance"
        open={open.value}
        onToggle={() => setOpen((o) => ({ ...o, value: !o.value }))}
      >
        <ValueComparisonGauge {...vehicle} />
      </CollapsibleCard>

      {/* How It Compares */}
      {comparison && (
        <CollapsibleCard
          title="How It Compares"
          open={open.compare}
          onToggle={() => setOpen((o) => ({ ...o, compare: !o.compare }))}
        >
          <ComparisonBars {...comparison} />
        </CollapsibleCard>
      )}

      {/* Ownership Costs */}
      <CollapsibleCard
        title="Ownership Costs"
        open={open.ownership}
        onToggle={() => setOpen((o) => ({ ...o, ownership: !o.ownership }))}
      >
        <OwnershipCostChart {...vehicle} />
      </CollapsibleCard>

      {/* What Others Say (Social Proof) */}
      <CollapsibleCard
        title="What Others Say"
        open={open.social}
        onToggle={() => setOpen((o) => ({ ...o, social: !o.social }))}
      >
        <TrendingNow trending={trending} />
        <VehicleActivity activity={activity} />
      </CollapsibleCard>

      {/* Safety & Reliability */}
      <CollapsibleCard
        title="Safety & Reliability"
        open={open.safety}
        onToggle={() => setOpen((o) => ({ ...o, safety: !o.safety }))}
      >
        <div className="flex flex-col gap-2">
          <SafetyStars {...safety} />
          <ReliabilityGauge {...reliability} />
        </div>
      </CollapsibleCard>

      {/* Will It Fit? */}
      <CollapsibleCard
        title="Will It Fit?"
        open={open.fit}
        onToggle={() => setOpen((o) => ({ ...o, fit: !o.fit }))}
      >
        <WillItFitVisualization {...fit} />
      </CollapsibleCard>
    </div>
  );
}

type CollapsibleCardProps = {
  title: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
};

function CollapsibleCard({ title, open, onToggle, children }: CollapsibleCardProps) {
  return (
    <div className="rounded-xl border border-imperial-border dark:border-imperial-border-dark bg-imperial-bg-light dark:bg-imperial-bg-dark shadow-sm">
      <button
        className="w-full flex items-center justify-between px-4 py-3 font-semibold text-imperial-primary dark:text-imperial-primary-light focus:outline-none"
        onClick={onToggle}
        aria-expanded={!!open}
        aria-controls={title.replace(/\s+/g, "-").toLowerCase()}
      >
        <span>{title}</span>
        <span className={`transition-transform duration-300 ${open ? '' : 'rotate-180'}`}>▼</span>
      </button>
      <div
        id={title.replace(/\s+/g, "-").toLowerCase()}
        className={`transition-all duration-300 ease-out overflow-hidden ${open ? 'max-h-[1000px] opacity-100' : 'max-h-0 opacity-0'}`}
      >
        <div className="px-4 pb-4">{children}</div>
      </div>
    </div>
  );
}
