import { InboxIcon } from "lucide-react";
import type { ElementType, PropsWithChildren } from "react";

interface EmptyProps {
  icon?: ElementType;
  title: string;
  description?: string;
}

export function Empty({ icon: Icon = InboxIcon, title, description, children }: PropsWithChildren<EmptyProps>) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5 text-white/25">
        <Icon size={28} />
      </div>
      <h3 className="text-sm font-medium text-white/60">{title}</h3>
      {description && <p className="mt-1 text-xs text-white/35 max-w-xs">{description}</p>}
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}
