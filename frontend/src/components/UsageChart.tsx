import type { HistoryModelUsage } from "../types";
import { clsx } from "../utils";

const colors = ["#36f2e6", "#b8ff5e", "#ffbd4a", "#ff4d8d", "#8ab4ff", "#d7f8ff"];

function polarPoint(cx: number, cy: number, radius: number, angle: number) {
  const radians = ((angle - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(radians),
    y: cy + radius * Math.sin(radians),
  };
}

function arcPath(cx: number, cy: number, radius: number, startAngle: number, endAngle: number) {
  const start = polarPoint(cx, cy, radius, endAngle);
  const end = polarPoint(cx, cy, radius, startAngle);
  const largeArc = endAngle - startAngle <= 180 ? "0" : "1";
  return `M ${cx} ${cy} L ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 0 ${end.x} ${end.y} Z`;
}

export function UsageChart({
  usage,
  title,
  className,
}: {
  usage: HistoryModelUsage[];
  title: string;
  className?: string;
}) {
  const total = usage.reduce((sum, item) => sum + item.inputTokens + item.outputTokens, 0);
  let cursor = 0;

  return (
    <div className={clsx("grid gap-4 md:grid-cols-[180px_minmax(0,1fr)] md:items-center", className)}>
      <div className="relative mx-auto h-44 w-44">
        <svg viewBox="0 0 120 120" role="img" aria-label={title} className="h-full w-full">
          <circle cx="60" cy="60" r="56" fill="#0b111b" stroke="rgba(255,255,255,0.10)" />
          {total === 0 ? (
            <circle cx="60" cy="60" r="38" fill="rgba(255,255,255,0.04)" />
          ) : (
            usage.map((item, index) => {
              const value = item.inputTokens + item.outputTokens;
              const start = cursor;
              const end = cursor + (value / total) * 360;
              cursor = end;
              return (
                <path
                  key={item.model}
                  d={arcPath(60, 60, 54, start, end)}
                  fill={colors[index % colors.length]}
                  opacity={0.92}
                />
              );
            })
          )}
          <circle cx="60" cy="60" r="31" fill="#05060a" stroke="rgba(255,255,255,0.10)" />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-[11px] uppercase tracking-[0.16em] text-slate-500">tokens</span>
          <span className="font-display text-xl font-semibold text-white">{total.toLocaleString()}</span>
        </div>
      </div>

      <div className="min-w-0 space-y-2">
        <p className="font-display text-lg font-semibold text-white">{title}</p>
        {usage.length === 0 ? (
          <p className="text-sm text-slate-500">No model usage</p>
        ) : (
          usage.map((item, index) => {
            const value = item.inputTokens + item.outputTokens;
            const percent = total ? Math.round((value / total) * 100) : 0;
            return (
              <div key={item.model} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 text-xs">
                <span
                  className="h-2.5 w-2.5"
                  style={{ backgroundColor: colors[index % colors.length] }}
                />
                <span className="truncate text-slate-300">{item.model}</span>
                <span className="font-semibold text-slate-100">
                  {value.toLocaleString()} / {percent}%
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
