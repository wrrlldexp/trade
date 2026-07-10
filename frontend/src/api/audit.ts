import { apiClient } from "./client";
import type { AuditLogEntry } from "./types";

export async function listAudit() {
  const { data } = await apiClient.get<AuditLogEntry[]>("/api/audit/");
  return data;
}
