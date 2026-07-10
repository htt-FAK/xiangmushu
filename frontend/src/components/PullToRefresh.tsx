import { useCallback, useEffect, useRef, useState } from "react";

const THRESHOLD = 80;
const MAX_PULL = 120;

export function PullToRefresh({ children }: { children: React.ReactNode }) {
  const [pulling, setPulling] = useState(false);
  const [pullDistance, setPullDistance] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const startY = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleTouchStart = useCallback((e: TouchEvent) => {
    // Only activate when scrolled to top
    if (window.scrollY > 5) return;
    startY.current = e.touches[0].clientY;
    setPulling(true);
  }, []);

  const handleTouchMove = useCallback((e: TouchEvent) => {
    if (!pulling || refreshing) return;
    const delta = e.touches[0].clientY - startY.current;
    if (delta > 0 && window.scrollY <= 0) {
      // Dampen the pull
      setPullDistance(Math.min(delta * 0.5, MAX_PULL));
      // passive listener — cannot preventDefault
    }
  }, [pulling, refreshing]);

  const handleTouchEnd = useCallback(() => {
    if (!pulling) return;
    setPulling(false);
    if (pullDistance >= THRESHOLD && !refreshing) {
      setRefreshing(true);
      window.location.reload();
    } else {
      setPullDistance(0);
    }
  }, [pulling, pullDistance, refreshing]);

  useEffect(() => {
    // Only enable on mobile
    if (window.innerWidth >= 1024) return;

    document.addEventListener("touchstart", handleTouchStart, { passive: true });
    document.addEventListener("touchmove", handleTouchMove, { passive: true });
    document.addEventListener("touchend", handleTouchEnd, { passive: true });

    return () => {
      document.removeEventListener("touchstart", handleTouchStart);
      document.removeEventListener("touchmove", handleTouchMove);
      document.removeEventListener("touchend", handleTouchEnd);
    };
  }, [handleTouchStart, handleTouchMove, handleTouchEnd]);

  const showIndicator = pullDistance > 10 || refreshing;
  const ready = pullDistance >= THRESHOLD;

  return (
    <>
      {showIndicator && (
        <div
          className="fixed inset-x-0 top-0 z-40 flex items-center justify-center overflow-hidden bg-night-950/80 backdrop-blur-sm transition-all duration-200"
          style={{ height: Math.max(pullDistance, refreshing ? 48 : 0) }}
        >
          <span className={`text-xs font-semibold transition-colors ${ready || refreshing ? "text-signal-cyan" : "text-slate-500"}`}>
            {refreshing ? "⟳ Refreshing..." : ready ? "↓ Release to refresh" : "↓ Pull to refresh"}
          </span>
        </div>
      )}
      <div
        ref={containerRef}
        className="transition-transform duration-100 will-change-transform"
        style={{ transform: pullDistance > 0 ? `translateY(${pullDistance}px)` : undefined }}
      >
        {children}
      </div>
    </>
  );
}
