import clsx from "clsx";
import type { HTMLAttributes, PropsWithChildren } from "react";

import { GlassCard } from "./AdaptiveLayout";

export function Card({ children, className, ...props }: PropsWithChildren<HTMLAttributes<HTMLDivElement>>) {
  return (
    <GlassCard className={clsx(className)} {...props}>
      {children}
    </GlassCard>
  );
}
