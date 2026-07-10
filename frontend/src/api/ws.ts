import { useEffect, useRef, useState } from "react";

import type { BotLogEntry } from "./types";
import { API_URL } from "./client";
import { useAuthStore } from "../store/auth";

function getWsUrl(path: string): string {
  let wsBase: string;
  if (API_URL) {
    wsBase = API_URL.replace(/^http/, "ws");
  } else {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    wsBase = `${proto}//${window.location.host}`;
  }
  const token = useAuthStore.getState().tokens?.access_token;
  const url = `${wsBase}${path}`;
  return token ? `${url}?token=${token}` : url;
}

function useReconnectingWebSocket(
  path: string,
  onMessage: (data: string) => void,
  deps: unknown[] = [],
) {
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const mountedRef = useRef(true);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    mountedRef.current = true;
    retryRef.current = 0;

    function connect() {
      if (!mountedRef.current) return;
      const socket = new WebSocket(getWsUrl(path));
      wsRef.current = socket;

      socket.onopen = () => {
        retryRef.current = 0;
      };

      socket.onmessage = (event) => {
        onMessageRef.current(event.data);
      };

      socket.onclose = () => {
        if (!mountedRef.current) return;
        const delay = Math.min(1000 * 2 ** retryRef.current, 30000);
        retryRef.current++;
        setTimeout(connect, delay);
      };

      socket.onerror = () => {
        socket.close();
      };
    }

    connect();

    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

export function useGridEvents(gridId: string) {
  const [messages, setMessages] = useState<string[]>([]);

  useReconnectingWebSocket(
    `/ws/grids/${gridId}`,
    (data) => {
      setMessages((current) => [data, ...current].slice(0, 50));
    },
    [gridId],
  );

  return messages;
}

export function useLogStream() {
  const [logs, setLogs] = useState<BotLogEntry[]>([]);

  useReconnectingWebSocket(
    "/ws/logs",
    (data) => {
      try {
        const entry = JSON.parse(data) as BotLogEntry;
        setLogs((current) => [entry, ...current].slice(0, 100));
      } catch {
        // ignore malformed messages
      }
    },
    [],
  );

  return logs;
}
