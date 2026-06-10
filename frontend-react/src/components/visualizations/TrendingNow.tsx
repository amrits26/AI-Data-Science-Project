import React from "react";

type TrendingVehicle = {
  image_url?: string;
  make?: string;
  model?: string;
  year?: number;
  price?: number;
  views?: number;
  inquiries?: number;
  isPopular?: boolean;
};

type TrendingNowProps = {
  trending?: TrendingVehicle[];
};

// Props: trending: [{ image_url, make, model, year, price, views, inquiries, isPopular }]
export default function TrendingNow({ trending = [] }: TrendingNowProps) {
  if (!trending.length) return null;
  return (
    <div className="flex gap-2 overflow-x-auto py-2">
      {trending.map((v, idx) => (
        <div key={idx} className="min-w-[120px] max-w-[140px] bg-imperial-bg-light dark:bg-imperial-bg-dark rounded-lg shadow p-2 flex flex-col items-center border border-imperial-border dark:border-imperial-border-dark relative">
          {v.isPopular && (
            <span className="absolute top-1 right-1 bg-imperial-gold text-imperial-primary text-[10px] font-bold px-2 py-0.5 rounded-full">Popular</span>
          )}
          {v.image_url && <img src={v.image_url} alt={`${v.year} ${v.make} ${v.model}`} className="w-20 h-14 object-cover rounded mb-1" />}
          <div className="text-xs font-semibold text-imperial-text dark:text-imperial-text-dark text-center">
            {v.year ?? ""} {v.make ?? ""} {v.model ?? ""}
          </div>
          <div className="text-xs text-imperial-gold font-bold">${v.price?.toLocaleString()}</div>
          <div className="flex flex-col items-center mt-1 gap-0.5">
            {(v.views ?? 0) > 0 && <span className="text-[10px] text-imperial-text-secondary">👁 {v.views} views</span>}
            {(v.inquiries ?? 0) > 0 && <span className="text-[10px] text-imperial-text-secondary">💬 {v.inquiries} inquiries</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
