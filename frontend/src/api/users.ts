import { apiClient } from "./client";
import type { User } from "./types";

export async function createUser(payload: {
  email: string;
  full_name: string;
  password: string;
  role: string;
}) {
  const { data } = await apiClient.post<User>("/api/users/", payload);
  return data;
}

export async function listUsers() {
  const { data } = await apiClient.get<User[]>("/api/users/");
  return data;
}

export async function inviteUser(email: string, role: string) {
  const { data } = await apiClient.post<{ token: string; invite_url: string }>("/api/users/invites", {
    email,
    role,
  });
  return data;
}

export async function updateUser(userId: string, payload: { role?: string; is_active?: boolean }) {
  const { data } = await apiClient.patch<User>(`/api/users/${userId}`, payload);
  return data;
}

export async function resetUserPassword(userId: string, newPassword: string) {
  const { data } = await apiClient.post<{ success: boolean }>(`/api/users/${userId}/reset-password`, {
    new_password: newPassword,
  });
  return data;
}

export async function deleteUser(userId: string) {
  const { data } = await apiClient.delete<{ success: boolean }>(`/api/users/${userId}`);
  return data;
}
