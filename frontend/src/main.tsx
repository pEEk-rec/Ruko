import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { registerServiceWorker } from "./pwa/register";
import "./styles/tokens.css";
import "./styles/app.css";
import "./styles/refresh.css";

// The fictional broker demo is loaded only when its address is opened, so it never adds to
// the first download of the real app.
const BrokerApp = lazy(() =>
  import("./mock-broker/BrokerApp").then((module) => ({ default: module.BrokerApp })),
);
const isDemoBroker = window.location.pathname === "/demo/broker";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {isDemoBroker ? (
      <Suspense fallback={null}>
        <BrokerApp />
      </Suspense>
    ) : (
      <App />
    )}
  </StrictMode>,
);

if (import.meta.env.PROD) void registerServiceWorker();
