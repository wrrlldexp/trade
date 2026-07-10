import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuthStore } from "../store/auth";
import type { UserRole } from "../api/types";

export function ProtectedRoute({ roles }: { roles?: UserRole[] }) {
  const user = useAuthStore((state) => state.user);
  const isGuest = useAuthStore((state) => state.isGuest);
  const isInitializing = useAuthStore((state) => state.isInitializing);
  const location = useLocation();

  if (isInitializing) {
    return null;
  }

  if (!user && !isGuest) {
    return <Navigate to="/login" replace />;
  }

  if (isGuest && location.pathname !== "/dashboard") {
    return <Navigate to="/dashboard" replace />;
  }

  if (user && roles && !roles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }
  return <Outlet />;
}
