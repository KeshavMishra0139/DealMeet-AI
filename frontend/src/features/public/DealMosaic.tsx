// The hero's motion background: three columns of tiles drifting forever, neighbours in
// opposite directions, each tile one idea from DealMeet AI (connect your accounts, your
// next moves, a fair price, audience fit, escrow, getting paid). Decorative: no numbers,
// no names, nothing a visitor could mistake for data.
//
// Between them sit black-and-white photo tiles, from assets/mosaic/photos.ts; a photo slot
// with no photo there is left out.
//
// Motion is CSS (`--animate-tiles-up/down`): each column holds its tiles twice and slides by
// half its height, so the loop has no seam, at the same speed whatever the column holds.
// Columns ease in once on load, pause while the hero is off-screen, and stand still with
// reduced motion.
import { motion, useInView } from "framer-motion";
import { BadgeCheck, FileText, ShieldCheck } from "lucide-react";
import { useRef } from "react";
import { siInstagram, siYoutube, type SimpleIcon } from "simple-icons";
import { MOSAIC_PHOTOS, type MosaicPhoto } from "@/assets/mosaic/photos";
import { LogoMark } from "@/components/shared/Wordmark";
import { cn } from "@/lib/utils";

type Kind = "instagram" | "youtube" | "moves" | "price" | "brand" | "escrow" | "fit" | "collective" | "hindi" | "kit" | "paid";
/** An idea tile, or photo slot N (MOSAIC_PHOTOS[N]). */
type Slot = Kind | { photo: number };

/** The content runs up in the outer columns and down in the middle. */
const COLUMNS: { tiles: Slot[]; dir: "up" | "down"; offset: string }[] = [
  { tiles: ["instagram", { photo: 0 }, "moves", "brand", { photo: 3 }, "escrow", "fit"], dir: "up", offset: "" },
  { tiles: ["price", { photo: 1 }, "collective", "youtube", { photo: 4 }, "hindi", "paid"], dir: "down", offset: "-translate-y-[3.5%]" },
  // Moves in step with the first column: no idea tile here matches the first column's in the
  // same row or a neighbouring one, and repeats are light tiles only.
  { tiles: ["kit", { photo: 2 }, "fit", "youtube", "moves", { photo: 5 }, "paid"], dir: "up", offset: "-translate-y-[1.5%]" },
];

const SECONDS_PER_TILE = 3.6; // about a third of a tile a second

/** A column's tiles, leaving out photo slots that have no photo. */
function fill(tiles: Slot[]): (Kind | MosaicPhoto)[] {
  return tiles.flatMap<Kind | MosaicPhoto>((t) => {
    if (typeof t === "string") return [t];
    const photo = MOSAIC_PHOTOS[t.photo];
    return photo ? [photo] : [];
  });
}

const EXPO_OUT = [0.16, 1, 0.3, 1] as const;

export function DealMosaic({ className }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  // Nothing moves while the hero is scrolled away.
  const onScreen = useInView(ref);
  return (
    <div ref={ref} aria-hidden className={cn("pointer-events-none overflow-hidden [contain:paint]", className)}>
      <div className="grid h-full grid-cols-3 gap-2.5 lg:gap-3">
        {COLUMNS.map((col, i) => (
          <Column key={i} index={i} dir={col.dir} offset={col.offset} tiles={fill(col.tiles)} paused={!onScreen} />
        ))}
      </div>
    </div>
  );
}

function Column({ index, dir, offset, tiles, paused }: { index: number; dir: "up" | "down"; offset: string; tiles: (Kind | MosaicPhoto)[]; paused: boolean }) {
  return (
    <motion.div
      className={offset}
      initial={{ opacity: 0, y: dir === "up" ? 72 : -72 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 1.6, ease: EXPO_OUT, delay: 0.2 + index * 0.12 }}
    >
      {/* pb matches the gap, so each copy is exactly half the column. */}
      <div
        className={cn(
          "flex flex-col gap-2.5 pb-2.5 will-change-transform lg:gap-3 lg:pb-3 motion-reduce:animate-none",
          dir === "up" ? "animate-tiles-up" : "animate-tiles-down",
          paused && "[animation-play-state:paused]",
        )}
        style={{ animationDuration: `${tiles.length * SECONDS_PER_TILE}s` }}
      >
        {[...tiles, ...tiles].map((t, j) => (typeof t === "string" ? <Tile key={j} kind={t} /> : <PhotoTile key={j} photo={t} />))}
      </div>
    </motion.div>
  );
}

const BASE =
  "tile-grain relative isolate flex aspect-[4/5] w-full shrink-0 flex-col justify-between overflow-hidden rounded-[18px] p-2.5 shadow-[inset_0_1px_0_rgb(255_255_255/0.5),0_18px_40px_-28px_rgb(10_27_51/0.45)] sm:p-3.5 lg:rounded-[22px] lg:p-4";
const DARK = "[--grain-blend:screen] [--grain-opacity:0.06]";
const LABEL = "font-display text-[11px] font-medium leading-tight sm:text-[13px] lg:text-[14px]";

/** Black and white, with grain and a soft vignette, so any photo sits with the others. */
function PhotoTile({ photo }: { photo: MosaicPhoto }) {
  return (
    <div className={cn(BASE, "justify-end bg-[#d6d3d1] [--grain-opacity:0.1]")}>
      <img
        src={photo.src}
        alt=""
        decoding="async"
        fetchPriority="low"
        draggable={false}
        className="absolute inset-0 -z-10 size-full object-cover contrast-[1.06] grayscale"
        style={{ objectPosition: photo.position ?? "50% 50%" }}
      />
      <span className="absolute inset-0 -z-10 bg-[radial-gradient(120%_90%_at_50%_35%,transparent_55%,rgb(10_27_51/0.28))]" />
      {photo.caption && (
        <span className={cn(LABEL, "self-start rounded-full bg-white/85 px-2.5 py-1 text-[#0a1b33] backdrop-blur-sm")}>{photo.caption}</span>
      )}
    </div>
  );
}

function Brand({ icon, className }: { icon: SimpleIcon; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={cn("size-6 sm:size-8 lg:size-11", className)}>
      <path d={icon.path} fill={`#${icon.hex}`} />
    </svg>
  );
}

function Bar({ w, className }: { w: string; className: string }) {
  return <span className={cn("block h-1.5 rounded-full", className)} style={{ width: w }} />;
}

function Tile({ kind }: { kind: Kind }) {
  switch (kind) {
    case "instagram":
      return (
        <div className={cn(BASE, "bg-[#fce7f3] text-[#831843]")}>
          <Brand icon={siInstagram} />
          <span className={LABEL}>Connect Instagram</span>
        </div>
      );
    case "youtube":
      return (
        <div className={cn(BASE, "bg-[#faf7f2] text-[#0a1b33] ring-1 ring-[#e9e6df] ring-inset")}>
          <Brand icon={siYoutube} />
          <span className={LABEL}>Connect YouTube</span>
        </div>
      );
    case "moves":
      return (
        <div className={cn(BASE, "bg-[#ede9fe] text-[#4c1d95]")}>
          <span className={LABEL}>Next 3 moves</span>
          <span className="space-y-1.5">
            {["78%", "62%", "48%"].map((w, n) => (
              <span key={w} className="flex items-center gap-1.5">
                <span className="grid size-4 shrink-0 place-items-center rounded-full bg-white text-[9px] font-semibold text-[#6d28d9] lg:size-5 lg:text-[10px]">{n + 1}</span>
                <Bar w={w} className="bg-[#c4b5fd]" />
              </span>
            ))}
          </span>
        </div>
      );
    case "price":
      return (
        <div className={cn(BASE, "bg-signature text-white")}>
          <span className={LABEL}>Fair price</span>
          <span className="space-y-2">
            <span className="relative block h-1.5 rounded-full bg-white/30">
              <span className="absolute inset-y-0 left-[28%] right-[24%] rounded-full bg-white" />
            </span>
            <span className="block text-[10px] leading-tight text-white/85 sm:text-[11px]">A range, with reasons</span>
          </span>
        </div>
      );
    case "brand":
      return (
        <div className={cn(BASE, DARK, "items-start bg-[#0a1b33] text-white")}>
          <LogoMark className="size-9 sm:size-12 lg:size-16" />
          <span className={cn(LABEL, "text-white/80")}>Creators meet brands</span>
        </div>
      );
    case "escrow":
      return (
        <div className={cn(BASE, "bg-[#ffedd5] text-[#7c2d12]")}>
          <ShieldCheck className="size-6 text-[#c2410c] sm:size-7 lg:size-10" strokeWidth={1.5} />
          <span className="space-y-2">
            {/* Offer, funded, posted, paid: the deal rail. */}
            <span className="flex items-center">
              {[0, 1, 2, 3].map((n) => (
                <span key={n} className="flex flex-1 items-center last:flex-none">
                  <span className={cn("size-2 shrink-0 rounded-full", n < 3 ? "bg-[#ea580c]" : "border border-[#ea580c] bg-transparent")} />
                  {n < 3 && <span className="h-px flex-1 bg-[#fdba74]" />}
                </span>
              ))}
            </span>
            <span className={cn(LABEL, "block")}>Paid through escrow</span>
          </span>
        </div>
      );
    case "fit":
      return (
        <div className={cn(BASE, "bg-[#e0f2fe] text-[#0c4a6e]")}>
          {/* A creator's audience and a brand's target, overlapping. */}
          <svg viewBox="0 0 48 32" className="h-7 w-auto sm:h-9 lg:h-12">
            <circle cx="18" cy="16" r="12" fill="#7c3aed" fillOpacity="0.18" stroke="#7c3aed" strokeWidth="1.5" />
            <circle cx="30" cy="16" r="12" fill="#db2777" fillOpacity="0.18" stroke="#db2777" strokeWidth="1.5" />
          </svg>
          <span className={LABEL}>Audience fit</span>
        </div>
      );
    case "collective":
      return (
        <div className={cn(BASE, "bg-[#fef3c7] text-[#78350f]")}>
          <span className="flex -space-x-2">
            {["#c4b5fd", "#f9a8d4", "#fdba74", "#93c5fd"].map((c) => (
              <span key={c} className="size-5 rounded-full ring-2 ring-[#fef3c7] sm:size-7 lg:size-9" style={{ background: c }} />
            ))}
          </span>
          <span className={LABEL}>Book a collective</span>
        </div>
      );
    case "hindi":
      return (
        <div className={cn(BASE, DARK, "bg-[#1e1b3a] text-white")}>
          <span lang="hi" className="font-sans text-xl font-semibold leading-none sm:text-3xl lg:text-[44px]">
            हिंदी
          </span>
          <span className={cn(LABEL, "text-white/75")}>
            English or <span lang="hi">हिंदी</span>
          </span>
        </div>
      );
    case "kit":
      return (
        <div className={cn(BASE, "bg-white text-[#0a1b33] ring-1 ring-slate-200 ring-inset")}>
          <FileText className="size-6 text-slate-600 sm:size-7 lg:size-10" strokeWidth={1.5} />
          <span className="space-y-1.5">
            <Bar w="70%" className="bg-slate-200" />
            <Bar w="52%" className="bg-slate-200" />
            <span className={cn(LABEL, "block pt-1")}>Media kit</span>
          </span>
        </div>
      );
    case "paid":
      return (
        <div className={cn(BASE, "bg-[#d1fae5] text-[#064e3b]")}>
          <BadgeCheck className="size-6 text-[#047857] sm:size-7 lg:size-10" strokeWidth={1.5} />
          <span className={LABEL}>Paid on approval</span>
        </div>
      );
  }
}
