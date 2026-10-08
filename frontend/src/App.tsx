import { lazy, Suspense, type ReactNode } from "react";
import { Route, Routes } from "react-router-dom";
import { Upcoming } from "@/features/public/Upcoming";

const Landing = lazy(() => import("@/features/public/Landing"));
const Login = lazy(() => import("@/features/public/Login"));
const NotFound = lazy(() => import("@/features/public/NotFound"));
const CreatorShell = lazy(() => import("@/features/creator/CreatorShell"));
const BrandShell = lazy(() => import("@/features/brand/BrandShell"));

const soon = (title: string, body: string): ReactNode => <Upcoming title={title} body={body} />;

function Fallback() {
  return <div className="min-h-dvh" aria-busy="true" aria-label="Loading" />;
}

export default function App() {
  return (
    <Suspense fallback={<Fallback />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />

        <Route path="/creator" element={<CreatorShell />}>
          <Route index element={soon("Your next 3 moves", "The Next-Step Engine arrives in Phase 2.")} />
          <Route path="roadmap" element={soon("Growth roadmap", "Content gaps, skills, reference twins and a 30-day plan arrive in Phase 2.")} />
          <Route path="money" element={soon("Money paths", "Ranked monetisation paths and the Fair-Price waterfall arrive in Phase 2.")} />
          <Route path="opportunities" element={soon("Opportunities", "The consent-based marketplace arrives in Phase 3.")} />
          <Route path="deals" element={soon("Deals", "The deal rail arrives in Phase 4.")} />
          <Route path="kit" element={soon("Media kit and link-in-bio", "Arrives in Phase 4.")} />
          <Route path="privacy" element={soon("Privacy and consent", "The consent ledger arrives in Phase 3.")} />
        </Route>

        <Route path="/brand" element={<BrandShell />}>
          <Route index element={soon("Overview", "Campaigns, escrow and deals by stage arrive in Phase 3.")} />
          <Route path="campaigns" element={soon("Campaigns", "Arrives in Phase 3.")} />
          <Route path="campaigns/new" element={soon("New campaign", "Arrives in Phase 3.")} />
          <Route path="deals" element={soon("Deals", "Arrives in Phase 4.")} />
          <Route path="profile" element={soon("Brand profile", "Arrives in Phase 3.")} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
