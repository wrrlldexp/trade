import clsx from "clsx";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import { createContext, type PropsWithChildren, useCallback, useContext, useEffect, useRef, useState } from "react";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

let nextId = 0;

export function ToastProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timersRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  useEffect(() => {
    const timers = timersRef.current;
    return () => { timers.forEach(clearTimeout); timers.clear(); };
  }, []);

  const toast = useCallback((message: string, type: ToastType = "info") => {
    const id = ++nextId;
    setToasts((prev) => [...prev, { id, message, type }]);
    const timer = setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
      timersRef.current.delete(id);
    }, 3500);
    timersRef.current.set(id, timer);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div role="status" aria-live="polite" className="fixed bottom-20 sm:bottom-6 right-4 left-4 sm:left-auto sm:w-80 z-[60] flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={clsx(
              "pointer-events-auto flex items-start gap-3 rounded-2xl border p-3.5 text-sm shadow-lg backdrop-blur-xl animate-in slide-in-from-bottom-2 fade-in duration-200",
              t.type === "success" && "border-emerald-400/20 bg-emerald-950/80 text-emerald-100",
              t.type === "error" && "border-red-400/20 bg-red-950/80 text-red-100",
              t.type === "info" && "border-white/10 bg-[#0b1220]/90 text-white/90",
            )}
          >
            {t.type === "success" && <CheckCircle2 size={18} className="shrink-0 mt-0.5 text-emerald-400" />}
            {t.type === "error" && <XCircle size={18} className="shrink-0 mt-0.5 text-red-400" />}
            {t.type === "info" && <Info size={18} className="shrink-0 mt-0.5 text-indigo-400" />}
            <span className="flex-1 leading-snug">{t.message}</span>
            <button onClick={() => dismiss(t.id)} className="shrink-0 p-0.5 text-white/40 hover:text-white/70" aria-label="Закрыть">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
