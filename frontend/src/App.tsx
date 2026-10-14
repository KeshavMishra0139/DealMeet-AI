import { lazy, Suspense } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { EmbedBridge, PhoneStage, PhoneToggle, usePhoneShortcut } from "@/components/demo/PhoneMode";
import { RequireSession } from "@/components/shared/AuthGate";
import { LangScope } from "@/i18n";
import { usePhoneMode } from "@/lib/phone";
import { isEmbedFrame } from "@/lib/session";

const Landing = lazy(() => import("@/features/public/Landing"));
const Login = lazy(() => import("@/features/public/Login"));
const LoginComplete = lazy(() => import("@/features/public/LoginComplete"));
const NotFound = lazy(() => import("@/features/public/NotFound"));
const CreatorShell = lazy(() => import("@/features/creator/CreatorShell"));
const BrandShell = lazy(() => import("@/features/brand/BrandShell"));
const HelpCenter = lazy(() => import("@/components/shared/HelpCenter"));
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
const Worth = lazy(() => import("@/features/public/Worth"));
const Brands = lazy(() => import("@/features/public/Brands"));
const BrandPage = lazy(() => import("@/features/public/BrandPage"));
const CreatorDreamBrands = lazy(() => import("@/features/creator/DreamBrands"));
const CreatorPitches = lazy(() => import("@/features/creator/Pitches"));
const PitchShare = lazy(() => import("@/features/public/PitchShare"));
const BrandFanInbox = lazy(() => import("@/features/brand/FanInbox"));
const CreatorConnections = lazy(() => import("@/features/creator/Connections"));
const CreatorProfile = lazy(() => import("@/features/creator/Profile"));
const DemoCompare = lazy(() => import("@/features/demo/Compare"));
const DemoLive = lazy(() => import("@/features/demo/Live"));
const AdminConsole = lazy(() => import("@/features/admin/AdminConsole"));

const embedded = isEmbedFrame();

function Fallback() {
  return <div className="min-h-dvh" aria-busy="true" aria-label="Loading" />;
}

export default function App() {
  const phone = usePhoneMode();
  const { pathname } = useLocation();
  // /demo pages lay out their own phones; everywhere else P puts the app in a phone.
  const demoPage = pathname.startsWith("/demo");
  usePhoneShortcut(embedded, pathname !== "/demo/live");
  if (phone && !embedded && !demoPage) {
    return (
      <>
        <PhoneStage />
        <PhoneToggle />
      </>
    );
  }
  return (
    <Suspense fallback={<Fallback />}>
      {embedded ? <EmbedBridge /> : pathname !== "/demo/live" && <PhoneToggle />}
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/login/complete" element={<LoginComplete />} />
        <Route path="/c/:handle" element={<LinkInBio />} />
        <Route path="/worth" element={<Worth />} />
        <Route path="/brands" element={<Brands />} />
        <Route path="/brands/:slug" element={<BrandPage />} />
        <Route path="/p/:slug" element={<PitchShare />} />

        <Route
          path="/creator/onboarding"
          element={
            <LangScope>
              <RequireSession role="creator" needsProfile={false}>
                <CreatorOnboarding />
              </RequireSession>
            </LangScope>
          }
        />
        <Route path="/creator" element={<CreatorShell />}>
          <Route index element={<CreatorHome />} />
          <Route path="roadmap" element={<CreatorRoadmap />} />
          <Route path="money" element={<CreatorMoney />} />
          <Route path="opportunities" element={<CreatorOpportunities />} />
          <Route path="deals" element={<CreatorDeals />} />
          <Route path="deals/:id" element={<DealView role="creator" />} />
          <Route path="kit" element={<CreatorKit />} />
          <Route path="brands" element={<CreatorDreamBrands />} />
          <Route path="pitches" element={<CreatorPitches />} />
          <Route path="privacy" element={<CreatorPrivacy />} />
          <Route path="connections" element={<CreatorConnections />} />
          <Route path="help" element={<HelpCenter role="creator" />} />
          <Route path="profile" element={<CreatorProfile />} />
        </Route>

        <Route
          path="/brand/onboarding"
          element={
            <RequireSession role="brand" needsProfile={false}>
              <BrandOnboarding />
            </RequireSession>
          }
        />
        <Route path="/brand" element={<BrandShell />}>
          <Route index element={<BrandHome />} />
          <Route path="campaigns" element={<BrandCampaigns />} />
          <Route path="campaigns/new" element={<BrandNewCampaign />} />
          <Route path="campaigns/:id/edit" element={<BrandNewCampaign />} />
          <Route path="campaigns/:id" element={<BrandCampaign />} />
          <Route path="creators/:id" element={<BrandCreator />} />
          <Route path="deals" element={<BrandDeals />} />
          <Route path="deals/:id" element={<DealView role="brand" />} />
          <Route path="collectives/:id" element={<CollectiveDetail />} />
          <Route path="profile" element={<BrandProfile />} />
          <Route path="inbox" element={<BrandFanInbox />} />
          <Route path="help" element={<HelpCenter role="brand" />} />
        </Route>

        <Route path="/admin" element={<AdminConsole />} />
        <Route path="/demo/compare" element={<DemoCompare />} />
        <Route path="/demo/live" element={<DemoLive />} />

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
