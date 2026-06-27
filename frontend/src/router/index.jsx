import { createBrowserRouter, Navigate } from "react-router-dom";
import ChatPage from "../pages/ChatPage";
import LoginPage from "../pages/LoginPage";
import DashboardPage from "../pages/DashboardPage";
import KnowledgePage from "../pages/KnowledgePage";
import ToolCenterPage from "../pages/ToolCenterPage";
import WorkflowPage from "../pages/WorkflowPage";
import LogsPage from "../pages/LogsPage";
import SettingsPage from "../pages/SettingsPage";

function ProtectedRoute({ children }) {
  const token = localStorage.getItem("token");
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/", element: <ProtectedRoute><DashboardPage /></ProtectedRoute> },
  { path: "/chat", element: <ProtectedRoute><ChatPage /></ProtectedRoute> },
  { path: "/dashboard", element: <ProtectedRoute><DashboardPage /></ProtectedRoute> },
  { path: "/knowledge", element: <ProtectedRoute><KnowledgePage /></ProtectedRoute> },
  { path: "/tools", element: <ProtectedRoute><ToolCenterPage /></ProtectedRoute> },
  { path: "/workflow", element: <ProtectedRoute><WorkflowPage /></ProtectedRoute> },
  { path: "/logs", element: <ProtectedRoute><LogsPage /></ProtectedRoute> },
  { path: "/settings", element: <ProtectedRoute><SettingsPage /></ProtectedRoute> },
]);

export default router;
