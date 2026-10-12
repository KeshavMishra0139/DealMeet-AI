// Inter (body) and Outfit (display), self-hosted: no third-party font request, and the
// app keeps working offline.
import "@fontsource-variable/inter";
import "@fontsource-variable/outfit";
import "@fontsource/noto-sans-devanagari/400.css";
import "@fontsource/noto-sans-devanagari/600.css";
import "@fontsource/noto-sans-tamil/400.css";
import "@fontsource/noto-sans-tamil/600.css";
import "@fontsource/noto-sans-telugu/400.css";
import "@fontsource/noto-sans-kannada/400.css";
import "@fontsource/noto-sans-malayalam/400.css";
import "@fontsource/noto-sans-bengali/400.css";
import "@fontsource/noto-sans-gujarati/400.css";
import "./styles/index.css";

import { QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import App from "./App";
import { TooltipProvider } from "./components/ui/overlays";
import { I18nProvider } from "./i18n";
import { queryClient } from "./lib/api";
import { startSync } from "./lib/sync";

startSync(queryClient);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <I18nProvider>
          <TooltipProvider>
            <MotionConfig reducedMotion="user">
              <App />
              <Toaster position="top-center" richColors closeButton />
            </MotionConfig>
          </TooltipProvider>
        </I18nProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
