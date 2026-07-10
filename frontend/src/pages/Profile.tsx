import { useState } from "react";

import { changePassword, disable2FA, setup2FA, verify2FA } from "../api/auth";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { useAuthStore } from "../store/auth";

export function ProfilePage() {
  const user = useAuthStore((state) => state.user);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [secret, setSecret] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");

  return (
    <div className="space-y-5">
      <Card className="space-y-3">
        <h1 className="text-2xl font-bold">Профиль</h1>
        <div className="text-sm text-hint">
          {user?.full_name} · {user?.email}
        </div>
      </Card>
      <Card className="space-y-3">
        <h2 className="text-xl font-semibold">Смена пароля</h2>
        <Input value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} placeholder="Текущий пароль" type="password" />
        <Input value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="Новый пароль" type="password" />
        <Button
          onClick={async () => {
            try {
              await changePassword(currentPassword, newPassword);
              setMessage("Пароль обновлён");
              setCurrentPassword("");
              setNewPassword("");
            } catch {
              setMessage("Ошибка при смене пароля");
            }
          }}
        >
          Сохранить пароль
        </Button>
      </Card>
      <Card className="space-y-3">
        <h2 className="text-xl font-semibold">2FA</h2>
        <Button
          className="bg-secondary text-text"
          onClick={async () => {
            try {
              const response = await setup2FA();
              setSecret(response.secret);
              setMessage(response.qr_uri);
            } catch {
              setMessage("Ошибка при настройке 2FA");
            }
          }}
        >
          Получить QR URI
        </Button>
        {secret && (
          <>
            <Input value={code} onChange={(event) => setCode(event.target.value)} placeholder="Код 2FA" />
            <Button
              onClick={async () => {
                try {
                  await verify2FA(secret, code);
                  setMessage("2FA включена");
                } catch {
                  setMessage("Неверный код 2FA");
                }
              }}
            >
              Включить 2FA
            </Button>
            <Button
              className="bg-secondary text-text"
              onClick={async () => {
                try {
                  await disable2FA(currentPassword, code);
                  setMessage("2FA выключена");
                  setSecret("");
                  setCode("");
                } catch {
                  setMessage("Ошибка при отключении 2FA");
                }
              }}
            >
              Выключить 2FA
            </Button>
          </>
        )}
        {message && <div className="break-all text-sm text-hint">{message}</div>}
      </Card>
    </div>
  );
}
