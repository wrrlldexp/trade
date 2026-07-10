import { type PropsWithChildren, useEffect, useRef } from "react";

interface ModalProps {
  open?: boolean;
  title?: string;
  onClose: () => void;
}

export function Modal({ open = true, title, onClose, children }: PropsWithChildren<ModalProps>) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement as HTMLElement;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") { onCloseRef.current(); return; }
      if (e.key !== "Tab") return;
      const container = overlayRef.current;
      if (!container) return;
      const focusable = container.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
      previousFocus.current?.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      role="dialog"
      aria-modal="true"
      aria-label={title || "Диалог"}
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-lg max-h-[90dvh] flex flex-col rounded-t-3xl sm:rounded-3xl border border-white/10 bg-[#0b1220] text-white shadow-[0_24px_70px_rgba(0,0,0,0.45)]">
        <div className="flex items-center justify-between px-5 pt-5 pb-3 shrink-0">
          {title ? <h3 className="text-lg font-semibold">{title}</h3> : <div />}
          <button
            onClick={onClose}
            className="flex items-center justify-center w-11 h-11 rounded-full bg-white/10 text-white/70 hover:bg-white/20 active:bg-white/25 transition-colors text-lg shrink-0"
            aria-label="Закрыть"
          >
            ✕
          </button>
        </div>
        <div className="overflow-y-auto overscroll-contain px-5 pb-5 flex-1 min-h-0">
          {children}
        </div>
      </div>
    </div>
  );
}
