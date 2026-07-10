import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listAudit } from "../api/audit";
import { Card } from "../components/Card";
import { Modal } from "../components/Modal";

export function AuditPage() {
  const { data: entries = [] } = useQuery({ queryKey: ["audit"], queryFn: listAudit });
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <Card className="space-y-3">
      <h1 className="text-2xl font-bold">Аудит</h1>
      {entries.map((entry) => (
        <button
          type="button"
          key={entry.id}
          className="block w-full rounded-2xl bg-secondary p-4 text-left"
          onClick={() => setSelected(JSON.stringify(entry.payload, null, 2))}
        >
          <div className="font-semibold">{entry.action}</div>
          <div className="text-sm text-hint">{entry.created_at}</div>
        </button>
      ))}
      <Modal open={Boolean(selected)} title="Payload" onClose={() => setSelected(null)}>
        <pre className="overflow-auto rounded-2xl bg-secondary p-4 text-xs">{selected}</pre>
      </Modal>
    </Card>
  );
}
