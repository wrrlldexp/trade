import clsx from "clsx";
import type { CSSProperties, HTMLAttributes, PropsWithChildren, ReactNode } from "react";

export const Screen = {
  get width() {
    return typeof window === "undefined" ? 393 : window.innerWidth;
  },
  get height() {
    return typeof window === "undefined" ? 852 : window.innerHeight;
  },
  get scale() {
    return typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;
  },
  get safeAreaTop() {
    if (typeof window === "undefined") return 47;
    return Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--safe-top")) || 0;
  },
  get safeAreaBottom() {
    if (typeof window === "undefined") return 34;
    return Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--safe-bottom")) || 0;
  },
  get hasDynamicIsland() {
    return this.safeAreaTop > 50;
  },
};

type AdaptiveAxis = "x" | "y";

function scaleForAxis(axis: AdaptiveAxis) {
  const base = axis === "x" ? 393 : 852;
  const current = axis === "x" ? Screen.width : Screen.height;
  return current / base;
}

export function adaptiveHPadding(base = 16): CSSProperties {
  const scale = scaleForAxis("x");
  const value = Math.max(12, Math.min(base * scale, base * 1.35));
  return { paddingLeft: value, paddingRight: value };
}

export function adaptiveVPadding(base = 16): CSSProperties {
  const scale = scaleForAxis("y");
  const value = Math.max(12, Math.min(base * scale, base * 1.35));
  return { paddingTop: value, paddingBottom: value };
}

export function adaptiveFrame(width?: number, height?: number): CSSProperties {
  const xScale = scaleForAxis("x");
  const yScale = scaleForAxis("y");
  return {
    width: width === undefined ? undefined : width * xScale,
    height: height === undefined ? undefined : height * yScale,
  };
}

export function adaptiveFont(size: number, weight: CSSProperties["fontWeight"] = 400): CSSProperties {
  const scale = Math.min(Screen.width / 393, 1.3);
  return {
    fontSize: size * scale,
    fontWeight: weight,
  };
}

export function GlassCard({
  children,
  className = "",
  padding = "p-4 sm:p-5",
  ...props
}: PropsWithChildren<
  HTMLAttributes<HTMLDivElement> & {
    className?: string;
    padding?: string;
  }
>) {
  return (
    <div
      className={clsx(
        "rounded-2xl sm:rounded-[28px] border border-white/10 bg-white/5 shadow-[0_20px_70px_rgba(15,23,42,0.18)] backdrop-blur-xl overflow-hidden",
        padding,
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function ScreenContainer({
  children,
  title,
  actions,
  className = "",
}: PropsWithChildren<{ title?: string; actions?: ReactNode; className?: string }>) {
  return (
    <div className={`relative min-h-[100dvh] overflow-hidden bg-[#08090f] text-white ${className}`}>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.22),transparent_34%),radial-gradient(circle_at_80%_10%,rgba(16,185,129,0.14),transparent_28%),linear-gradient(180deg,#08090f_0%,#0b1020_58%,#06070b_100%)]" />
      <div className="absolute -right-20 top-10 h-72 w-72 rounded-full bg-indigo-500/10 blur-3xl" />
      <div className="absolute left-0 top-1/2 h-72 w-72 rounded-full bg-emerald-400/10 blur-3xl" />

      <div className="relative mx-auto flex min-h-[100dvh] w-full max-w-[1400px] flex-col px-4 py-4 sm:px-6 lg:px-8">
        {(title || actions) && (
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              {title && <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">{title}</h1>}
            </div>
            {actions}
          </div>
        )}
        <div className="flex-1">{children}</div>
      </div>
    </div>
  );
}
