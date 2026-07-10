import clsx from "clsx";
import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, PropsWithChildren } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
}

export function Button({
  className,
  children,
  loading,
  disabled,
  ...props
}: PropsWithChildren<ButtonProps>) {
  return (
    <button
      className={clsx(
        "rounded-2xl border border-white/10 bg-white/10 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-white/15 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40",
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      <span className="inline-flex items-center gap-2">
        {loading && <Loader2 className="animate-spin shrink-0" size={16} />}
        {children}
      </span>
    </button>
  );
}
