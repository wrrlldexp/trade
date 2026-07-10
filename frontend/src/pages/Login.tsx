import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { login, loginWith2FA } from "../api/auth";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { ScreenContainer } from "../components/AdaptiveLayout";
import { useAuthStore } from "../store/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);
  const temporaryToken = useAuthStore((state) => state.temporaryToken);
  const setTemporaryToken = useAuthStore((state) => state.setTemporaryToken);
  const setGuestMode = useAuthStore((state) => state.setGuestMode);
  const setWelcomeSeen = useAuthStore((state) => state.setWelcomeSeen);
  const setProfileName = useAuthStore((state) => state.setProfileName);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async () => {
    setError(null);
    try {
      if (temporaryToken) {
        const response = await loginWith2FA(temporaryToken, code);
        if (response.tokens && response.user) {
          setAuth(response.user, response.tokens);
          navigate("/dashboard");
        }
        return;
      }

      const response = await login(email, password);
      if (response.requires_2fa && response.temporary_token) {
        setTemporaryToken(response.temporary_token);
        return;
      }
      if (response.tokens && response.user) {
        setAuth(response.user, response.tokens);
        navigate("/dashboard");
      }
    } catch (submitError) {
      setError("Не удалось войти");
    }
  };

  return (
    <ScreenContainer className="flex items-start justify-center">
      <div className="w-full max-w-3xl py-6 sm:py-10">
        <Card className="space-y-4">
          <div>
            <div className="text-xs uppercase tracking-[0.3em] text-white/50">MoneyBot v2</div>
            <h1 className="mt-2 text-3xl font-bold text-white">Вход в панель</h1>
            <p className="mt-2 text-sm leading-6 text-white/60">
              Используйте рабочий аккаунт, либо вернитесь к приветственному экрану и настройте профиль позже.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <Input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" />
            <Input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Пароль"
              type="password"
            />
          </div>
          {temporaryToken && (
            <Input value={code} onChange={(event) => setCode(event.target.value)} placeholder="Код 2FA" />
          )}
          {error && <div className="text-sm text-red-300">{error}</div>}
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button
              className="flex-1 border-transparent bg-gradient-to-r from-indigo-500 to-cyan-400 text-white shadow-[0_18px_40px_rgba(79,70,229,0.3)] hover:brightness-110"
              onClick={onSubmit}
            >
              {temporaryToken ? "Подтвердить 2FA" : "Войти"}
            </Button>
            <Button
              className="border border-white/10 bg-white/5 text-white hover:bg-white/10"
              onClick={() => {
                setWelcomeSeen(true);
                setProfileName("Гость");
                setGuestMode(true);
                navigate("/dashboard", { replace: true });
              }}
              type="button"
            >
              Продолжить без входа
            </Button>
          </div>
          <div className="flex flex-col gap-2 text-sm sm:flex-row sm:items-center sm:justify-between">
            <button
              className="text-white/60 underline-offset-4 transition hover:text-white hover:underline"
              onClick={() => navigate("/welcome")}
              type="button"
            >
              Вернуться к приветствию
            </button>
            <span className="text-white/35">Скип доступен для демо-режима</span>
          </div>
        </Card>
      </div>
    </ScreenContainer>
  );
}
