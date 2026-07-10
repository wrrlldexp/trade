import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { fetchMe } from "./api/auth";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Spinner } from "./components/Spinner";
import { useAuthStore } from "./store/auth";

const WelcomePage = lazy(() => import("./pages/Welcome").then(m => ({ default: m.WelcomePage })));
const LoginPage = lazy(() => import("./pages/Login").then(m => ({ default: m.LoginPage })));
const AcceptInvitePage = lazy(() => import("./pages/AcceptInvite").then(m => ({ default: m.AcceptInvitePage })));
const DashboardPage = lazy(() => import("./pages/Dashboard").then(m => ({ default: m.DashboardPage })));
const GridListPage = lazy(() => import("./pages/GridList").then(m => ({ default: m.GridListPage })));
const GridCreatePage = lazy(() => import("./pages/GridCreate").then(m => ({ default: m.GridCreatePage })));
const GridDetailPage = lazy(() => import("./pages/GridDetail").then(m => ({ default: m.GridDetailPage })));
const ChartPage = lazy(() => import("./pages/Chart").then(m => ({ default: m.ChartPage })));
const AccountsPage = lazy(() => import("./pages/Accounts").then(m => ({ default: m.AccountsPage })));
const ProfilePage = lazy(() => import("./pages/Profile").then(m => ({ default: m.ProfilePage })));
const LogsPage = lazy(() => import("./pages/Logs").then(m => ({ default: m.LogsPage })));
const TradesPage = lazy(() => import("./pages/Trades").then(m => ({ default: m.TradesPage })));
const MonitoringPage = lazy(() => import("./pages/Monitoring").then(m => ({ default: m.MonitoringPage })));
const UsersPage = lazy(() => import("./pages/Users").then(m => ({ default: m.UsersPage })));
const AuditPage = lazy(() => import("./pages/Audit").then(m => ({ default: m.AuditPage })));

function PageLoader() {
  return (
    <div className="flex items-center justify-center py-20">
      <Spinner />
    </div>
  );
}

export default function App() {
  const user = useAuthStore((state) => state.user);
  const hasSeenWelcome = useAuthStore((state) => state.hasSeenWelcome);
  const isGuest = useAuthStore((state) => state.isGuest);
  const tokens = useAuthStore((state) => state.tokens);
  const setAuth = useAuthStore((state) => state.setAuth);
  const logout = useAuthStore((state) => state.logout);
  const setInitializing = useAuthStore((state) => state.setInitializing);

  useEffect(() => {
    if (!tokens?.access_token || user) {
      setInitializing(false);
      return;
    }
    void fetchMe()
      .then((me) => {
        if (tokens) {
          setAuth(me, tokens);
        }
      })
      .catch(() => logout())
      .finally(() => setInitializing(false));
  }, [logout, setAuth, setInitializing, tokens, user]);

  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route
          path="/"
          element={
            <Navigate
              to={hasSeenWelcome ? (user || isGuest ? "/dashboard" : "/login") : "/welcome"}
              replace
            />
          }
        />
        <Route path="/welcome" element={<WelcomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/invite/:token" element={<AcceptInvitePage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<Layout><DashboardPage /></Layout>} />
          <Route path="/grids" element={<Layout><GridListPage /></Layout>} />
          <Route path="/grids/new" element={<Layout><GridCreatePage /></Layout>} />
          <Route path="/grids/:gridId" element={<Layout><GridDetailPage /></Layout>} />
          <Route path="/chart" element={<Layout><ChartPage /></Layout>} />
          <Route path="/accounts" element={<Layout><AccountsPage /></Layout>} />
          <Route path="/profile" element={<Layout><ProfilePage /></Layout>} />
        </Route>
        <Route element={<ProtectedRoute />}>
          <Route path="/logs" element={<Layout><LogsPage /></Layout>} />
          <Route path="/trades" element={<Layout><TradesPage /></Layout>} />
          <Route path="/monitoring" element={<Layout><MonitoringPage /></Layout>} />
          <Route path="/users" element={<Layout><UsersPage /></Layout>} />
          <Route path="/audit" element={<Layout><AuditPage /></Layout>} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
