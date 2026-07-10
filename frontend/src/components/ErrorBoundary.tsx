import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[100dvh] bg-[#08090f] flex items-center justify-center p-8">
          <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-8 max-w-lg w-full text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-400/10 text-red-400 text-xl">!</div>
            <h1 className="text-lg font-semibold text-white mb-2">
              Произошла ошибка
            </h1>
            <p className="text-sm text-white/50 mb-6">
              {this.state.error?.message || "Неизвестная ошибка"}
            </p>
            <button
              type="button"
              className="rounded-2xl border border-white/10 bg-white/10 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-white/15 active:scale-[0.98]"
              onClick={() => window.location.reload()}
            >
              Перезагрузить
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
