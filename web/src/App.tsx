import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import type { AuthTokens } from "./api/client";
import { useLocalStorage } from "./hooks/useLocalStorage";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import TicketDetail from "./pages/TicketDetail";

export type Session = AuthTokens & {
  email: string;
};

function App() {
  const [session, setSession] = useLocalStorage<Session | null>("supportpilot.session", null);
  const navigate = useNavigate();

  function handleLogin(nextSession: Session) {
    setSession(nextSession);
    navigate("/tickets");
  }

  function handleLogout() {
    setSession(null);
    navigate("/login");
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={session ? <Navigate to="/tickets" replace /> : <Login onLogin={handleLogin} />}
      />
      <Route
        path="/tickets"
        element={
          session ? (
            <Dashboard session={session} onLogout={handleLogout} />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route
        path="/tickets/:ticketId"
        element={
          session ? (
            <TicketDetail session={session} onLogout={handleLogout} />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route path="*" element={<Navigate to={session ? "/tickets" : "/login"} replace />} />
    </Routes>
  );
}

export default App;
