import { apiClient } from "./client";
import type { LoginResponse, TokenPair, User } from "./types";

export async function login(email: string, password: string) {
  const { data } = await apiClient.post<LoginResponse>("/api/auth/login", { email, password });
  return data;
}

export async function loginWith2FA(temporaryToken: string, code: string) {
  const { data } = await apiClient.post<LoginResponse>("/api/auth/login/2fa", {
    temporary_token: temporaryToken,
    code,
  });
  return data;
}

export async function fetchMe() {
  const { data } = await apiClient.get<User>("/api/auth/me");
  return data;
}

export async function refresh(refreshToken: string) {
  const { data } = await apiClient.post<TokenPair>("/api/auth/refresh", {
    refresh_token: refreshToken,
  });
  return data;
}

export async function logout(accessToken: string, refreshToken: string) {
  const { data } = await apiClient.post<{ success: boolean }>("/api/auth/logout", {
    access_token: accessToken,
    refresh_token: refreshToken,
  });
  return data;
}

export async function setup2FA() {
  const { data } = await apiClient.post<{ secret: string; qr_uri: string }>("/api/auth/2fa/setup");
  return data;
}

export async function verify2FA(secret: string, code: string) {
  void secret;
  const { data } = await apiClient.post<{ success: boolean }>("/api/auth/2fa/verify", { code });
  return data;
}

export async function disable2FA(password: string, code: string) {
  const { data } = await apiClient.post<{ success: boolean }>("/api/auth/2fa/disable", {
    password,
    code,
  });
  return data;
}

export async function acceptInvite(token: string, fullName: string, password: string) {
  const { data } = await apiClient.post<User>("/api/auth/invites/accept", {
    token,
    full_name: fullName,
    password,
  });
  return data;
}

export async function changePassword(currentPassword: string, newPassword: string) {
  const { data } = await apiClient.post<{ success: boolean }>("/api/auth/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
  return data;
}
