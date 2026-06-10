import React from "react";

// Props: rating (1-5)
export default function SafetyStars({ rating = 0 }) {
  const stars = [1, 2, 3, 4, 5];
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-semibold text-imperial-text-secondary dark:text-imperial-text-secondary-dark mr-1">NHTSA Overall Safety Rating:</span>
      {stars.map((s) => (
        <span
          key={s}
          className={`text-2xl ${s <= rating ? "text-imperial-gold glow-star" : "text-imperial-border dark:text-imperial-border-dark"}`}
          style={{ filter: s <= rating ? "drop-shadow(0 0 4px #d4a84388)" : undefined }}
        >
          ★
        </span>
      ))}
    </div>
  );
}
