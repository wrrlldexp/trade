import clsx from "clsx";
import type { PropsWithChildren, SelectHTMLAttributes } from "react";

export function Select({ children, className, ...props }: PropsWithChildren<SelectHTMLAttributes<HTMLSelectElement>>) {
  return (
    <select
      {...props}
      className={clsx(
        "w-full appearance-none rounded-2xl border border-white/10 bg-[#0f1629] px-3 py-2.5 pr-8 text-base sm:text-sm text-white outline-none transition-colors focus:border-indigo-400/60 focus:ring-2 focus:ring-indigo-500/20 disabled:opacity-40 disabled:pointer-events-none [&>option]:bg-[#0f1629] [&>option]:text-white",
        "bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22rgba(255%2C255%2C255%2C0.5)%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22m6%209%206%206%206-6%22%2F%3E%3C%2Fsvg%3E')] bg-[position:right_0.75rem_center] bg-no-repeat",
        className,
      )}
    >
      {children}
    </select>
  );
}
