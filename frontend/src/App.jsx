import { RouterProvider } from "react-router-dom";
import router from "./router";
import "./App.css";
import { ChatProvider } from "./contexts/ChatContext";

export default function App() {
  return (
    <ChatProvider>
      <RouterProvider router={router} />
    </ChatProvider>
  );
}
