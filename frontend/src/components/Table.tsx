import type { PropsWithChildren } from "react";

export function Table({ children }: PropsWithChildren) {
  return <div className="overflow-x-auto rounded-3xl border border-white/10 bg-white/5">{children}</div>;
}
