import axios from "axios";

import { useAuthStore } from "../store/auth";

const API_URL = import.meta.env.VITE_API_URL || "";

export { API_URL };

export const apiClient = axios.create({
  baseURL: API_URL,
});

const refreshClient = axios.create({ baseURL: API_URL });

apiClient.interceptors.request.use((config) => {
  const tokens = useAuthStore.getState().tokens;
  if (tokens?.access_token) {
    config.headers.Authorization = `Bearer ${tokens.access_token}`;
  }
  return config;
});

// Queue for requests waiting on token refresh
let refreshPromise: Promise<unknown> | null = null;

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as { _retry?: boolean } & typeof error.config;
    if (error.response?.status === 401 && !originalRequest?._retry) {
      originalRequest._retry = true;
      const tokens = useAuthStore.getState().tokens;
      if (!tokens?.refresh_token) {
        useAuthStore.getState().logout();
        return Promise.reject(error);
      }
      try {
        // If a refresh is already in progress, wait for it
        if (!refreshPromise) {
          refreshPromise = refreshClient
            .post("/api/auth/refresh", { refresh_token: tokens.refresh_token })
            .then((response) => {
              const nextTokens = response.data;
              const user = useAuthStore.getState().user;
              if (user) {
                useAuthStore.getState().setAuth(user, nextTokens);
              }
              return nextTokens;
            })
            .finally(() => {
              refreshPromise = null;
            });
        }
        await refreshPromise;
        const freshTokens = useAuthStore.getState().tokens;
        originalRequest.headers.Authorization = `Bearer ${freshTokens?.access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        useAuthStore.getState().logout();
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  },
);
