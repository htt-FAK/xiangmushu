import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth";
import { I18nProvider } from "./i18n";
import "./styles.css";
import { WorkflowProvider } from "./workflow";
import { BackgroundSessionsProvider } from "./backgroundSessions";
import { ToastProvider } from "./components/Toast";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <I18nProvider>
          <WorkflowProvider>
            <ToastProvider>
              <BackgroundSessionsProvider>
                <App />
              </BackgroundSessionsProvider>
            </ToastProvider>
          </WorkflowProvider>
        </I18nProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
