import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { acceptInvite } from "../api/auth";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { ScreenContainer } from "../components/AdaptiveLayout";

export function AcceptInvitePage() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    try {
      await acceptInvite(token, fullName, password);
      navigate("/login");
    } catch {
      setError("Не удалось принять приглашение");
    }
  };

  return (
    <ScreenContainer className="flex items-start justify-center">
      <div className="w-full max-w-2xl py-6 sm:py-10">
        <Card className="space-y-4">
          <div>
            <div className="text-xs uppercase tracking-[0.3em] text-white/50">Invite flow</div>
            <h1 className="text-2xl font-bold text-white">Принять приглашение</h1>
          </div>
          <Input value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Полное имя" />
          <Input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Пароль" type="password" />
          {error && <div className="text-sm text-red-300">{error}</div>}
          <Button
            className="w-full border-transparent bg-gradient-to-r from-indigo-500 to-cyan-400 text-white shadow-[0_18px_40px_rgba(79,70,229,0.3)] hover:brightness-110"
            onClick={onSubmit}
          >
            Создать аккаунт
          </Button>
        </Card>
      </div>
    </ScreenContainer>
  );
}
