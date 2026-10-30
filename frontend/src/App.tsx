import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import SaraAvatar from "./components/SaraAvatar";
import { AuthProvider, useAuth } from "./lib/auth";
import Account from "./pages/Account";
import AppLayout from "./pages/AppLayout";
import Admin from "./pages/Admin";
import AskSara from "./pages/AskSara";
import { Login, Register } from "./pages/Auth";
import { Destination, ExploreList } from "./pages/Explore";
import Guide from "./pages/Guide";
import Landing from "./pages/Landing";
import Plan from "./pages/Plan";
import Strategist from "./pages/Strategist";
import Trips from "./pages/Trips";

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) {
    return (
      <div className="grid h-dvh place-items-center bg-cream">
        <Loader2 className="animate-spin text-mustard-600" size={28} />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <>{children}</>;
}

function NotFound() {
  return (
    <div className="grid h-dvh place-items-center bg-cream px-4 text-center">
      <div>
        <SaraAvatar size={72} mood="alert" className="mx-auto" />
        <h1 className="mt-4 text-3xl font-extrabold">This road doesn't exist</h1>
        <p className="mt-1 text-ink-500">Even Sara couldn't find it on the map.</p>
        <Link to="/" className="btn-primary mt-5">Back home</Link>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/app" element={<Protected><AppLayout /></Protected>}>
            <Route index element={<Plan />} />
            <Route path="ask" element={<AskSara />} />
            <Route path="explore" element={<ExploreList />} />
            <Route path="explore/:slug" element={<Destination />} />
            <Route path="guide" element={<Guide />} />
            <Route path="admin" element={<Admin />} />
            <Route path="strategist" element={<Strategist />} />
            <Route path="trips" element={<Trips />} />
            <Route path="account" element={<Account />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
