import clsx from "clsx";
import type { PropsWithChildren } from "react";

export function Badge({ children, tone = "neutral" }: PropsWithChildren<{ tone?: "neutral" | "good" | "warn" | "error" }>) {
  return (
    <span
      className={clsx("inline-flex rounded-full px-2 py-1 text-xs font-semibold", {
        "border border-white/10 bg-white/5 text-white/75": tone === "neutral",
        "border border-emerald-400/20 bg-emerald-400/10 text-emerald-100": tone === "good",
        "border border-amber-400/20 bg-amber-400/10 text-amber-100": tone === "warn",
        "border border-red-400/20 bg-red-400/10 text-red-100": tone === "error",
      })}
    >
      {children}
    </span>
  );
}
