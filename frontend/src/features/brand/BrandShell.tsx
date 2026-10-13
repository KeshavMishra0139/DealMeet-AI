import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Handshake, Inbox, LayoutDashboard, Megaphone, Menu, Plus, RotateCcw, Users } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { PageFade, ScrollProgress } from "@/components/motion/Motion";
import { ActionAssistant } from "@/components/shared/ActionAssistant";
import { AccountMenu, DeleteAccountButton } from "@/components/shared/AccountMenu";
import { RequireSession, SignOutButton } from "@/components/shared/AuthGate";
import { Avatar } from "@/components/shared/Bits";
import { Wordmark } from "@/components/shared/Wordmark";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { api, post } from "@/lib/api";
import { useDemoMode, useSharedDemo } from "@/lib/shared-demo";
import { useBrandId } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

export interface Brand {
  id: string;
  name: string;
  kind: string;
  category: string;
  description: string;
  hue: number;
  niches: string[];
  target: { ages: string[]; gender: string; regions: string[]; cities: string[]; languages: string[] };
  budget_monthly?: number;
  goal?: string;
  verified: boolean;
  created_at?: string;
  guest?: boolean;
}

const NAV = [
  { to: "/brand", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/brand/campaigns", label: "Campaigns", icon: Megaphone },
  { to: "/brand/deals", label: "Deals", icon: Handshake },
  { to: "/brand/inbox", label: "Fan Inbox", icon: Inbox },
  { to: "/brand/profile", label: "Brand profile", icon: Building2 },
];

export function useBrand() {
  const id = useBrandId();
  return useQuery({ queryKey: ["brand", id], queryFn: () => api<Brand>(`/brands/${id}`) });
}

export default function BrandShell() {
  useTheme("brand");
  return (
    <RequireSession role="brand">
      <Console />
    </RequireSession>
  );
}

function Console() {
  const brand = useBrand();
  const [open, setOpen] = useState(false);

  const nav = (onClick?: () => void) => (
    <nav aria-label="Brand Console" className="flex flex-col gap-0.5">
      {NAV.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onClick}
          className={({ isActive }) =>
            cn(
              "flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-[13.5px] font-medium transition-colors",
              isActive ? "bg-surface-2 text-fg" : "text-muted hover:bg-surface-2 hover:text-fg",
            )
          }
        >
          {({ isActive }) => (
            <>
              <item.icon className={cn("size-4", isActive && "text-accent")} aria-hidden />
              {item.label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="theme-brand min-h-dvh bg-bg text-fg">
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-accent px-3 py-2 text-accent-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
      >
        Skip to content
      </a>
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[232px] flex-col overflow-y-auto overscroll-contain border-r border-line bg-surface px-3 py-4 lg:flex">
        <Link to="/brand" className="mx-1.5 rounded-lg" aria-label="DealMeet AI: your Console home">
          <Wordmark />
        </Link>
        <AccountMenu role="brand" className="mt-5" links={[{ label: "Brand profile", to: "/brand/profile" }]}>
          <BrandSwitcher />
        </AccountMenu>
        <Button asChild variant="primary" size="sm" className="mx-0.5 mt-4 justify-start">
          <Link to="/brand/campaigns/new">
            <Plus aria-hidden /> New campaign
          </Link>
        </Button>
        <ActionAssistant role="brand" className="mx-0.5 mt-2 justify-start" />
        <div className="mt-4 flex-1">{nav()}</div>
        <Controls />
      </aside>

      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-line bg-surface/90 px-4 backdrop-blur lg:hidden">
        <Link to="/brand" className="rounded-lg" aria-label="DealMeet AI: your Console home">
          <Wordmark />
        </Link>
        <div className="flex items-center gap-1">
          <ActionAssistant role="brand" compact />
          <Button asChild variant="primary" size="sm">
            <Link to="/brand/campaigns/new">
              <Plus aria-hidden /> New
            </Link>
          </Button>
          <Button variant="ghost" size="icon-sm" aria-label="Menu" onClick={() => setOpen(true)}>
            <Menu />
          </Button>
        </div>
      </header>

      <div className="lg:pl-[232px]">
        <main id="main" className="mx-auto w-full max-w-[1200px] px-4 pb-16 pt-5 sm:px-6 lg:px-10 lg:pt-8">
          <ScrollProgress />
          <PageFade>
            <Outlet />
          </PageFade>
        </main>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent sheet title={brand.data?.name ?? "Menu"} description={brand.data?.category}>
          {nav(() => setOpen(false))}
          <div className="mt-4 border-t border-line pt-4">
            <Controls onDone={() => setOpen(false)} />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function BrandSwitcher({ className }: { className?: string }) {
  const brand = useBrand();
  if (!brand.data) return <div className={cn("skeleton h-[52px] rounded-xl", className)} />;
  return (
    <span className={cn("flex items-center gap-2.5 rounded-xl border border-line p-2 pr-8 transition-colors hover:bg-surface-2", className)}>
      <Avatar name={brand.data.name} hue={brand.data.hue} size={32} className="rounded-lg" />
      <span className="min-w-0">
        <span className="block truncate text-[13px] font-semibold">{brand.data.name}</span>
        <span className="block truncate text-xs text-muted">{brand.data.category}</span>
      </span>
    </span>
  );
}

function Controls({ onDone }: { onDone?: () => void }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [resetting, setResetting] = useState(false);
  const shared = useSharedDemo();
  const demo = useDemoMode();
  return (
    <div className="space-y-0.5">
      {demo && (
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start"
          onClick={() => {
            onDone?.();
            navigate("/login?role=brand");
          }}
        >
          <Users aria-hidden /> Switch brand
        </Button>
      )}
      {demo && (
        <Button
          variant="ghost"
          size="sm"
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
          {!resetting && <RotateCcw aria-hidden />} Reset demo
        </Button>
      )}
      <SignOutButton role="brand" onDone={onDone} size="sm" className="w-full justify-start" />
      <DeleteAccountButton role="brand" onDone={onDone} />
      {shared && <p className="px-3 pt-1 text-[11px] leading-snug text-muted">Shared demo: everyone sees the same data. Reset only when you start your own walkthrough.</p>}
    </div>
  );
}
