import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  Handshake,
  Heart,
  Home,
  IndianRupee,
  Inbox,
  Languages,
  Link2,
  Map as MapIcon,
  Menu,
  RotateCcw,
  Send,
  ShieldCheck,
  UserRound,
  Users,
} from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { PageFade, ParallaxAurora, ScrollProgress } from "@/components/motion/Motion";
import { RequireSession, SignOutButton } from "@/components/shared/AuthGate";
import { Avatar } from "@/components/shared/Bits";
import { ActionAssistant } from "@/components/shared/ActionAssistant";
import { AskButton } from "./AskPanel";
import { Wordmark } from "@/components/shared/Wordmark";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { LangScope, useI18n } from "@/i18n";
import type { Dict } from "@/i18n/en";
import { api, post } from "@/lib/api";
import { useDemoMode, useSharedDemo } from "@/lib/shared-demo";
import { isEmbedFrame, useCreatorId } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import type { Creator } from "@/lib/types";
import { cn } from "@/lib/utils";

type NavItem = { to: string; key: keyof Dict; short?: keyof Dict; icon: typeof Home; end?: boolean };

const PRIMARY: NavItem[] = [
  { to: "/creator", key: "nav.home", icon: Home, end: true },
  { to: "/creator/roadmap", key: "nav.roadmap", icon: MapIcon },
  { to: "/creator/money", key: "nav.money", icon: IndianRupee },
  { to: "/creator/opportunities", key: "nav.opportunities", short: "nav.opportunities.short", icon: Inbox },
  { to: "/creator/deals", key: "nav.deals", icon: Handshake },
];
const SECONDARY: NavItem[] = [
  { to: "/creator/brands", key: "nav.dream", icon: Heart },
  { to: "/creator/pitches", key: "nav.pitches", icon: Send },
  { to: "/creator/profile", key: "nav.profile", icon: UserRound },
  { to: "/creator/connections", key: "nav.connections", icon: Link2 },
  { to: "/creator/kit", key: "nav.kit", icon: FileText },
  { to: "/creator/privacy", key: "nav.privacy", icon: ShieldCheck },
];

export function useCreator() {
  const id = useCreatorId();
  return useQuery({ queryKey: ["creator", id], queryFn: () => api<Creator>(`/creators/${id}`) });
}

export default function CreatorShell() {
  return (
    <LangScope>
      <RequireSession role="creator">
        <Studio />
      </RequireSession>
    </LangScope>
  );
}

function Studio() {
  useTheme("creator");
  const { t } = useI18n();
  const creator = useCreator();
  const [moreOpen, setMoreOpen] = useState(false);
  const location = useLocation();
  const embedded = isEmbedFrame();

  return (
    <div className="theme-creator grain relative min-h-dvh">
      <ParallaxAurora />
      <ScrollProgress />
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-accent px-3 py-2 text-accent-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[248px] flex-col border-r border-line bg-[var(--bg)]/85 px-3 py-5 lg:flex">
        <Link to="/" className="mx-2 rounded-lg" aria-label="JodiDar AI home">
          <Wordmark />
        </Link>
        <ProfileCard creator={creator.data} className="mx-1 mt-6" />
        <AskButton className="mx-1 mt-3 justify-start" />
        <ActionAssistant role="creator" className="mx-1 mt-2 justify-start" />
        <nav aria-label="Creator Studio" className="mt-5 flex flex-1 flex-col gap-0.5">
          {[...PRIMARY, ...SECONDARY].map((item, i) => (
            <div key={item.to}>
              {i === PRIMARY.length && <div className="mx-3 my-3 h-px bg-line" />}
              <SideLink item={item} label={t(item.key)} />
            </div>
          ))}
        </nav>
        <ShellControls />
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-line bg-[var(--bg)]/92 px-4 lg:hidden">
        <Link to={embedded ? "/creator" : "/"} aria-label="JodiDar AI home" className="rounded-lg">
          <Wordmark />
        </Link>
        <div className="flex items-center gap-1">
          <AskButton compact />
          <ActionAssistant role="creator" compact />
          <LangToggle compact />
          <Button variant="ghost" size="icon-sm" aria-label={t("nav.more")} onClick={() => setMoreOpen(true)}>
            {creator.data ? (
              <Avatar name={creator.data.name} hue={creator.data.avatar_hue} size={28} generic={creator.data.is_reference} />
            ) : (
              <Menu />
            )}
          </Button>
        </div>
      </header>

      <div className="relative z-10 lg:pl-[248px]">
        <main
          id="main"
          className="mx-auto w-full max-w-[1000px] px-4 pb-[calc(96px+env(safe-area-inset-bottom))] pt-5 sm:px-6 lg:px-10 lg:pb-16 lg:pt-10"
        >
          <PageFade>
            <Outlet />
          </PageFade>
        </main>
      </div>

      {/* Mobile bottom tabs */}
      <nav
        aria-label="Creator Studio"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-[var(--bg)]/95 pb-[env(safe-area-inset-bottom)] lg:hidden"
      >
        <ul className="mx-auto grid max-w-md grid-cols-5">
          {PRIMARY.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex h-16 flex-col items-center justify-center gap-1 text-[11px] font-medium transition-colors",
                    isActive ? "text-fg" : "text-muted hover:text-fg-2",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={cn(
                        "grid h-7 w-12 place-items-center rounded-full transition-colors",
                        isActive && "bg-accent-soft text-accent",
                      )}
                    >
                      <item.icon className="size-[18px]" aria-hidden />
                    </span>
                    {t(item.short ?? item.key)}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <Dialog open={moreOpen} onOpenChange={setMoreOpen}>
        <DialogContent sheet title={creator.data?.name ?? t("nav.more")} description={creator.data ? `@${creator.data.handle}` : undefined}>
          <div className="space-y-1" key={location.pathname}>
            {SECONDARY.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMoreOpen(false)}
                className="flex h-12 items-center gap-3 rounded-xl px-3 text-[15px] text-fg-2 hover:bg-surface-2 hover:text-fg"
              >
                <item.icon className="size-5" aria-hidden />
                {t(item.key)}
              </NavLink>
            ))}
          </div>
          <div className="mt-4 border-t border-line pt-4">
            <ShellControls onDone={() => setMoreOpen(false)} />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SideLink({ item, label }: { item: NavItem; label: string }) {
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) =>
        cn(
          "group relative flex h-10 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-colors",
          isActive ? "bg-surface-2 text-fg" : "text-muted hover:bg-surface hover:text-fg",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && <span className="absolute inset-y-2 left-0 w-[3px] rounded-full bg-signature" aria-hidden />}
          <item.icon className={cn("size-[18px]", isActive && "text-accent")} aria-hidden />
          {label}
        </>
      )}
    </NavLink>
  );
}

function ProfileCard({ creator, className }: { creator?: Creator; className?: string }) {
  if (!creator) return <div className={cn("skeleton h-[60px] rounded-2xl", className)} />;
  return (
    <div className={cn("flex items-center gap-3 rounded-2xl border border-line bg-surface p-2.5", className)}>
      <Avatar name={creator.name} hue={creator.avatar_hue} size={38} generic={creator.is_reference} />
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold">{creator.name}</p>
        <p className="truncate text-xs text-muted">{creator.niche_label}</p>
      </div>
    </div>
  );
}

function LangToggle({ compact = false }: { compact?: boolean }) {
  const { lang, setLang, t } = useI18n();
  const next = lang === "en" ? "hi" : "en";
  return (
    <Button
      variant="ghost"
      size={compact ? "sm" : "md"}
      onClick={() => setLang(next)}
      aria-label={`${t("common.language")}: ${lang === "en" ? "English" : "हिंदी"}. Switch to ${next === "en" ? "English" : "Hindi"}`}
      className={cn(!compact && "w-full justify-start")}
    >
      <Languages aria-hidden />
      {compact ? (lang === "en" ? "हिं" : "EN") : lang === "en" ? "हिंदी में देखें" : "View in English"}
    </Button>
  );
}

function ShellControls({ onDone }: { onDone?: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [resetting, setResetting] = useState(false);
  const shared = useSharedDemo();
  const demo = useDemoMode();
  return (
    <div className="space-y-1">
      <div className="hidden lg:block">
        <LangToggle />
      </div>
      {demo && (
        <Button
          variant="ghost"
          className="w-full justify-start"
          onClick={() => {
            onDone?.();
            navigate("/login?role=creator");
          }}
        >
          <Users aria-hidden /> {t("common.switchProfile")}
        </Button>
      )}
      {demo && (
        <Button
          variant="ghost"
          className="w-full justify-start"
          loading={resetting}
          onClick={async () => {
            setResetting(true);
            await post("/demo/reset");
            await qc.invalidateQueries();
            setResetting(false);
            onDone?.();
          }}
        >
          {!resetting && <RotateCcw aria-hidden />} {t("common.resetDemo")}
        </Button>
      )}
      <SignOutButton role="creator" onDone={onDone} className="w-full justify-start" />
      {shared && <p className="px-3 pt-1 text-[11px] leading-snug text-muted">{t("common.sharedDemo")}</p>}
    </div>
  );
}
