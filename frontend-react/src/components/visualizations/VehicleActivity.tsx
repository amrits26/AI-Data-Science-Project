import React from "react";

type VehicleActivityData = {
  views?: number;
  inquiries?: number;
  lotSince?: string | null;
  isPopular?: boolean;
};

type VehicleActivityProps = {
  activity?: VehicleActivityData | null;
};

// Props: activity: { views, inquiries, lotSince, isPopular }
export default function VehicleActivity({ activity }: VehicleActivityProps) {
  if (!activity) return null;
  return (
    <div className="rounded-lg bg-imperial-bg-light dark:bg-imperial-bg-dark border border-imperial-border dark:border-imperial-border-dark p-3 mt-2 flex flex-col gap-1">
      {(activity.views ?? 0) > 0 && (
        <span className="text-xs text-imperial-text-secondary">👁 Viewed by {activity.views} shoppers this week</span>
      )}
      {(activity.inquiries ?? 0) > 0 && (
        <span className="text-xs text-imperial-text-secondary">💬 {activity.inquiries} customers have asked about this vehicle</span>
      )}
      {activity.lotSince && (
        <span className="text-xs text-imperial-text-secondary">📅 On our lot since {activity.lotSince}</span>
      )}
      {activity.isPopular && (
        <span className="inline-block bg-imperial-gold text-imperial-primary text-[10px] font-bold px-2 py-0.5 rounded-full mt-1">Popular</span>
      )}
    </div>
  );
}
