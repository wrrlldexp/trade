import clsx from "clsx";
import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
}

export function Input({ error, className, ...props }: InputProps) {
  return (
    <input
      {...props}
      className={clsx(
        "w-full rounded-2xl border bg-white/5 px-3 py-2.5 text-base sm:text-sm text-white outline-none placeholder:text-white/35 transition-colors",
        error
          ? "border-red-400/60 focus:border-red-400 focus:ring-2 focus:ring-red-500/20"
          : "border-white/10 focus:border-indigo-400/60 focus:ring-2 focus:ring-indigo-500/20",
        "disabled:opacity-40 disabled:pointer-events-none",
        className,
      )}
    />
  );
}
