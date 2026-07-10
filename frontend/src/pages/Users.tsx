import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, UserPlus } from "lucide-react";
import { useState } from "react";

import { createUser, deleteUser, inviteUser, listUsers, resetUserPassword, updateUser } from "../api/users";
import { useAuthStore } from "../store/auth";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { Modal } from "../components/Modal";
import { Select } from "../components/Select";

const ROLE_LABELS: Record<string, string> = {
  ultraadmin: "Ультра-Админ",
  superadmin: "Суперадмин",
  admin: "Администратор",
  viewer: "Наблюдатель",
};

export function UsersPage() {
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((state) => state.user);
  const isUltra = currentUser?.role === "ultraadmin";
  const canManage = isUltra || currentUser?.role === "superadmin";
  const { data: users = [] } = useQuery({ queryKey: ["users"], queryFn: listUsers });

  // Create user form
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ email: "", full_name: "", password: "", role: "admin" });
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  // Invite form
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("admin");
  const [inviteLink, setInviteLink] = useState("");

  // Reset password form (ultraadmin only)
  const [resetTarget, setResetTarget] = useState<{ id: string; email: string } | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);

  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["users"] });

  const handleCreate = async () => {
    setCreateError(null);
    if (!createForm.email || !createForm.full_name || !createForm.password) {
      setCreateError("Заполните все поля");
      return;
    }
    if (createForm.password.length < 8) {
      setCreateError("Пароль должен быть не менее 8 символов");
      return;
    }
    setCreating(true);
    try {
      await createUser(createForm);
      setShowCreate(false);
      setCreateForm({ email: "", full_name: "", password: "", role: "admin" });
      refresh();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setCreateError(detail === "User already exists" ? "Пользователь с таким email уже существует" : detail || "Ошибка создания");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Пользователи</h1>
        {canManage && (
          <div className="flex gap-2">
            <Button
              className="flex items-center gap-2 border-transparent bg-gradient-to-r from-indigo-500 to-cyan-400 text-white shadow-[0_12px_30px_rgba(79,70,229,0.25)] hover:brightness-110"
              onClick={() => setShowCreate(true)}
            >
              <Plus size={16} />
              Создать
            </Button>
            <Button onClick={() => { setShowInvite(true); setInviteLink(""); }}>
              <UserPlus size={16} className="mr-1 inline" />
              Пригласить
            </Button>
          </div>
        )}
      </div>

      {/* Users list */}
      <Card className="space-y-3">
        {users.length === 0 && <div className="text-sm text-white/40">Нет пользователей</div>}
        {users.map((user) => (
          <div
            key={user.id}
            className="flex flex-col gap-3 rounded-2xl bg-white/5 p-4 md:flex-row md:items-center md:justify-between"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-500/20 text-sm font-bold text-indigo-300">
                {user.full_name.charAt(0).toUpperCase()}
              </div>
              <div>
                <div className="font-semibold">{user.full_name}</div>
                <div className="text-sm text-white/50">{user.email}</div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Badge tone={user.is_active ? "good" : "warn"}>
                {user.is_active ? "Активен" : "Неактивен"}
              </Badge>
              {canManage && user.id !== currentUser?.id ? (
                <select
                  className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/70"
                  value={user.role}
                  onChange={async (e) => {
                    const newRole = e.target.value;
                    if (newRole === "ultraadmin" && !confirm("Назначить Ультра-Админ? Эта роль даёт полный контроль.")) return;
                    await updateUser(user.id, { role: newRole });
                    refresh();
                  }}
                >
                  {isUltra && <option value="ultraadmin">Ультра-Админ</option>}
                  <option value="superadmin">Суперадмин</option>
                  <option value="admin">Администратор</option>
                  <option value="viewer">Наблюдатель</option>
                </select>
              ) : (
                <span className={`rounded-full border px-2.5 py-0.5 text-xs ${user.role === "ultraadmin" ? "border-amber-400/30 bg-amber-400/10 text-amber-300" : "border-white/10 bg-white/5 text-white/70"}`}>
                  {ROLE_LABELS[user.role] || user.role}
                </span>
              )}
              {canManage && user.id !== currentUser?.id && (
                <>
                  <Button
                    className="bg-white/5 text-white/70 hover:bg-white/10"
                    onClick={async () => {
                      await updateUser(user.id, { is_active: !user.is_active });
                      refresh();
                    }}
                  >
                    {user.is_active ? "Деактивировать" : "Активировать"}
                  </Button>
                  {isUltra && (
                    <Button
                      className="bg-amber-500/10 text-amber-300 hover:bg-amber-500/20"
                      onClick={() => {
                        setResetTarget({ id: user.id, email: user.email });
                        setResetPassword("");
                        setResetError(null);
                      }}
                    >
                      Сменить пароль
                    </Button>
                  )}
                  <Button
                    className="bg-red-500/10 text-red-300 hover:bg-red-500/20"
                    onClick={async () => {
                      const msg = isUltra
                        ? `Полностью удалить аккаунт ${user.email}? Это необратимо.`
                        : `Деактивировать аккаунт ${user.email}?`;
                      if (!confirm(msg)) return;
                      await deleteUser(user.id);
                      refresh();
                    }}
                  >
                    {isUltra ? "Удалить" : "Деактивировать"}
                  </Button>
                </>
              )}
            </div>
          </div>
        ))}
      </Card>

      {/* Create user modal */}
      {showCreate && (
        <Modal onClose={() => setShowCreate(false)}>
          <div className="space-y-4">
            <h2 className="text-xl font-bold">Создать администратора</h2>
            <Input
              value={createForm.email}
              onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
              placeholder="Email"
              type="email"
            />
            <Input
              value={createForm.full_name}
              onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
              placeholder="Полное имя"
            />
            <Input
              value={createForm.password}
              onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
              placeholder="Пароль (мин. 8 символов)"
              type="password"
            />
            <Select
              value={createForm.role}
              onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}
            >
              <option value="admin">Администратор</option>
              <option value="viewer">Наблюдатель</option>
              <option value="superadmin">Суперадмин</option>
            </Select>
            {createError && <div className="text-sm text-red-300">{createError}</div>}
            <div className="flex gap-3">
              <Button
                className="flex-1 border-transparent bg-gradient-to-r from-indigo-500 to-cyan-400 text-white hover:brightness-110"
                onClick={handleCreate}
                disabled={creating}
              >
                {creating ? "Создание..." : "Создать аккаунт"}
              </Button>
              <Button className="bg-white/5 text-white/70" onClick={() => setShowCreate(false)}>
                Отмена
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Invite modal */}
      {showInvite && (
        <Modal onClose={() => setShowInvite(false)}>
          <div className="space-y-4">
            <h2 className="text-xl font-bold">Пригласить по ссылке</h2>
            <Input
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="Email"
              type="email"
            />
            <Select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}>
              <option value="admin">Администратор</option>
              <option value="viewer">Наблюдатель</option>
              <option value="superadmin">Суперадмин</option>
            </Select>
            <Button
              className="w-full border-transparent bg-gradient-to-r from-indigo-500 to-cyan-400 text-white hover:brightness-110"
              onClick={async () => {
                const res = await inviteUser(inviteEmail, inviteRole);
                setInviteLink(window.location.origin + res.invite_url);
              }}
            >
              Создать ссылку
            </Button>
            {inviteLink && (
              <div className="space-y-2">
                <div className="text-xs text-white/50">Отправьте эту ссылку пользователю:</div>
                <div
                  className="cursor-pointer rounded-xl bg-white/5 p-3 text-sm text-indigo-300 break-all"
                  onClick={() => navigator.clipboard.writeText(inviteLink)}
                >
                  {inviteLink}
                </div>
                <div className="text-xs text-white/40">Нажмите чтобы скопировать. Ссылка действует 7 дней.</div>
              </div>
            )}
            <Button className="w-full bg-white/5 text-white/70" onClick={() => setShowInvite(false)}>
              Закрыть
            </Button>
          </div>
        </Modal>
      )}
      {/* Reset password modal */}
      {resetTarget && (
        <Modal onClose={() => setResetTarget(null)}>
          <div className="space-y-4">
            <h2 className="text-xl font-bold">Сменить пароль</h2>
            <div className="text-sm text-white/50">{resetTarget.email}</div>
            <Input
              value={resetPassword}
              onChange={(e) => setResetPassword(e.target.value)}
              placeholder="Новый пароль (мин. 8 символов)"
              type="password"
            />
            {resetError && <div className="text-sm text-red-300">{resetError}</div>}
            <div className="flex gap-3">
              <Button
                className="flex-1 border-transparent bg-gradient-to-r from-amber-500 to-orange-400 text-white hover:brightness-110"
                onClick={async () => {
                  setResetError(null);
                  if (resetPassword.length < 8) {
                    setResetError("Пароль должен быть не менее 8 символов");
                    return;
                  }
                  setResetting(true);
                  try {
                    await resetUserPassword(resetTarget.id, resetPassword);
                    setResetTarget(null);
                  } catch (err: any) {
                    setResetError(err?.response?.data?.detail || "Ошибка смены пароля");
                  } finally {
                    setResetting(false);
                  }
                }}
                disabled={resetting}
              >
                {resetting ? "Сохранение..." : "Сменить пароль"}
              </Button>
              <Button className="bg-white/5 text-white/70" onClick={() => setResetTarget(null)}>
                Отмена
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
