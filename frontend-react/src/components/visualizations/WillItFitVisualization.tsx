import React from "react";

type FitInfo = {
  parking?: boolean;
  garage?: boolean;
  clearance?: number;
};

type WillItFitVisualizationProps = {
  length?: number;
  width?: number;
  type?: "car" | "truck" | "suv" | string;
  fitInfo?: FitInfo | null;
};

// Props: length (inches), width (inches), type ("car"|"truck"|"suv"), fitInfo: { parking: boolean, garage: boolean, clearance: number }
export default function WillItFitVisualization({ length = 0, width = 0, type, fitInfo }: WillItFitVisualizationProps) {
  // Standard parking: 216x108 in (18x9 ft)
  // Single garage: 240x144 in (20x12 ft)
  // Double garage: 240x264 in (20x22 ft)
  const parkingW = 108, parkingL = 216;
  const scale = Math.min(1, 180 / Math.max(length, parkingL));
  const carW = width * scale;
  const carL = length * scale;
  const spaceW = parkingW * scale;
  const spaceL = parkingL * scale;
  const clearance = fitInfo?.clearance ?? Math.round((parkingW - width) / 2);
  const fits = fitInfo?.parking ?? (width <= parkingW && length <= parkingL);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: spaceW, height: spaceL }}>
        {/* Parking space outline */}
        <div className="absolute left-0 top-0 w-full h-full border-2 border-dashed border-imperial-border dark:border-imperial-border-dark rounded-lg" />
        {/* Vehicle silhouette */}
        <div
          className={`absolute left-1/2 top-1/2 bg-imperial-primary/60 rounded-md shadow-lg`}
          style={{
            width: carW,
            height: carL,
            transform: `translate(-50%, -50%)`,
            zIndex: 2,
          }}
        />
      </div>
      <div className="flex flex-col items-center mt-2">
        <span className="text-xs text-imperial-text-secondary">Vehicle: {Math.round(length)}" L × {Math.round(width)}" W</span>
        <span className="text-xs text-imperial-text-secondary">Parking Space: 18' × 9' (216" × 108")</span>
        {fits && clearance > 12 && (
          <span className="text-xs text-imperial-success font-semibold">✓ Fits comfortably in standard parking ({clearance}" clearance each side)</span>
        )}
        {!fits && (
          <span className="text-xs text-imperial-gold font-semibold">⚠ Tight fit — may require careful parking ({clearance}" clearance)</span>
        )}
      </div>
    </div>
  );
}
