import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";

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
const BrandDeals = lazy(() => import("@/features/brand/BrandDeals"));
const CollectiveDetail = lazy(() => import("@/features/brand/CollectiveDetail"));
const CreatorDeals = lazy(() => import("@/features/creator/Deals"));
const CreatorKit = lazy(() => import("@/features/creator/Kit"));
const DealView = lazy(() => import("@/features/deals/DealView"));
const LinkInBio = lazy(() => import("@/features/public/LinkInBio"));

function Fallback() {
  return <div className="min-h-dvh" aria-busy="true" aria-label="Loading" />;
}

export default function App() {
  return (
    <Suspense fallback={<Fallback />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/c/:handle" element={<LinkInBio />} />

        <Route path="/creator/onboarding" element={<CreatorOnboarding />} />
        <Route path="/creator" element={<CreatorShell />}>
          <Route index element={<CreatorHome />} />
          <Route path="roadmap" element={<CreatorRoadmap />} />
          <Route path="money" element={<CreatorMoney />} />
          <Route path="opportunities" element={<CreatorOpportunities />} />
          <Route path="deals" element={<CreatorDeals />} />
          <Route path="deals/:id" element={<DealView role="creator" />} />
          <Route path="kit" element={<CreatorKit />} />
          <Route path="privacy" element={<CreatorPrivacy />} />
        </Route>

        <Route path="/brand/onboarding" element={<BrandOnboarding />} />
        <Route path="/brand" element={<BrandShell />}>
          <Route index element={<BrandHome />} />
          <Route path="campaigns" element={<BrandCampaigns />} />
          <Route path="campaigns/new" element={<BrandNewCampaign />} />
          <Route path="campaigns/:id" element={<BrandCampaign />} />
          <Route path="creators/:id" element={<BrandCreator />} />
          <Route path="deals" element={<BrandDeals />} />
          <Route path="deals/:id" element={<DealView role="brand" />} />
          <Route path="collectives/:id" element={<CollectiveDetail />} />
          <Route path="profile" element={<BrandProfile />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
