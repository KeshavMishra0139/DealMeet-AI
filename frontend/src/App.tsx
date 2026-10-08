import { lazy, Suspense, type ReactNode } from "react";
import { Route, Routes } from "react-router-dom";
import { Upcoming } from "@/features/public/Upcoming";

const Landing = lazy(() => import("@/features/public/Landing"));
const Login = lazy(() => import("@/features/public/Login"));
const NotFound = lazy(() => import("@/features/public/NotFound"));
const CreatorShell = lazy(() => import("@/features/creator/CreatorShell"));
const BrandShell = lazy(() => import("@/features/brand/BrandShell"));
const CreatorHome = lazy(() => import("@/features/creator/Home"));
const CreatorRoadmap = lazy(() => import("@/features/creator/Roadmap"));
const CreatorMoney = lazy(() => import("@/features/creator/Money"));
const CreatorOnboarding = lazy(() => import("@/features/creator/Onboarding"));
const CreatorOpportunities = lazy(() => import("@/features/creator/Opportunities"));
const CreatorPrivacy = lazy(() => import("@/features/creator/Privacy"));
const BrandHome = lazy(() => import("@/features/brand/BrandHome"));
const BrandCampaigns = lazy(() => import("@/features/brand/Campaigns"));
const BrandNewCampaign = lazy(() => import("@/features/brand/NewCampaign"));
const BrandCampaign = lazy(() => import("@/features/brand/Campaign"));
const BrandCreator = lazy(() => import("@/features/brand/BrandCreator"));
const BrandOnboarding = lazy(() => import("@/features/brand/BrandOnboarding"));
const BrandProfile = lazy(() => import("@/features/brand/BrandProfile"));

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

        <Route path="/creator/onboarding" element={<CreatorOnboarding />} />
        <Route path="/creator" element={<CreatorShell />}>
          <Route index element={<CreatorHome />} />
          <Route path="roadmap" element={<CreatorRoadmap />} />
          <Route path="money" element={<CreatorMoney />} />
          <Route path="opportunities" element={<CreatorOpportunities />} />
          <Route path="deals" element={soon("Deals", "The deal rail arrives in Phase 4.")} />
          <Route path="kit" element={soon("Media kit and link-in-bio", "Arrives in Phase 4.")} />
          <Route path="privacy" element={<CreatorPrivacy />} />
        </Route>

        <Route path="/brand/onboarding" element={<BrandOnboarding />} />
        <Route path="/brand" element={<BrandShell />}>
          <Route index element={<BrandHome />} />
          <Route path="campaigns" element={<BrandCampaigns />} />
          <Route path="campaigns/new" element={<BrandNewCampaign />} />
          <Route path="campaigns/:id" element={<BrandCampaign />} />
          <Route path="creators/:id" element={<BrandCreator />} />
          <Route path="deals" element={soon("Deals", "The deal rail arrives in Phase 4.")} />
          <Route path="deals/:id" element={soon("Deal", "The deal rail arrives in Phase 4.")} />
          <Route path="profile" element={<BrandProfile />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
