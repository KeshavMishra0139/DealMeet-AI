import { BatteryFull, Lock, Signal, Wifi } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { PHONE } from "@/lib/phone";
import { cn } from "@/lib/utils";

const BEZEL = 12;
const STATUS = 47;
const HOME = 21;
export const PHONE_OUTER = { width: PHONE.width + BEZEL * 2, height: PHONE.height + BEZEL * 2 };

export function useMediaQuery(query: string) {
  const [match, setMatch] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setMatch(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return match;
}

/**
 * Scale that fits a box of `w` x `h` inside the element's width and, when `fitHeight`
 * is on, the rest of the viewport below it. Never above 1.
 */
export function useFitScale(ref: RefObject<HTMLElement | null>, w: number, h: number, pad = 0, fitHeight = true) {
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      const availH = window.innerHeight - r.top - pad;
      setScale(Math.max(0.3, Math.min(1, r.width / w, fitHeight ? availH / h : 1)));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    window.addEventListener("resize", measure);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [ref, w, h, pad, fitHeight]);
  return scale;
}

function useLoaded(src: string) {
  const [loaded, setLoaded] = useState(false);
  useEffect(() => setLoaded(false), [src]);
  return [loaded, () => setLoaded(true)] as const;
}

/**
 * A CSS-only phone (390 x 844 screen) running the app in a same-origin frame.
 * `tone` matches the status bar to the screen it shows.
 */
export function PhoneFrame({
  src,
  title,
  tone = "dark",
  scale = 1,
  frameRef,
  label,
  className,
}: {
  src: string;
  title: string;
  tone?: "dark" | "light";
  scale?: number;
  frameRef?: RefObject<HTMLIFrameElement | null>;
  label?: React.ReactNode;
  className?: string;
}) {
  const [loaded, onLoad] = useLoaded(src);
  const screen = tone === "dark" ? "bg-[#0B0A1A] text-white" : "bg-[#F8F7FC] text-[#14121F]";
  return (
    <figure className={cn("flex flex-col items-center", className)}>
      <div style={{ width: PHONE_OUTER.width * scale, height: PHONE_OUTER.height * scale }}>
        <div
          className="relative origin-top-left rounded-[60px] bg-[#0E0D16] shadow-[0_0_0_1.5px_#2C2A3D,0_0_0_6px_#151320,0_40px_90px_-30px_rgb(0_0_0/0.75)]"
          style={{ width: PHONE_OUTER.width, height: PHONE_OUTER.height, padding: BEZEL, transform: `scale(${scale})` }}
        >
          {/* Side buttons */}
          <span aria-hidden className="absolute -left-[7px] top-[150px] h-[34px] w-[3px] rounded-l-sm bg-[#2C2A3D]" />
          <span aria-hidden className="absolute -left-[7px] top-[210px] h-[62px] w-[3px] rounded-l-sm bg-[#2C2A3D]" />
          <span aria-hidden className="absolute -left-[7px] top-[284px] h-[62px] w-[3px] rounded-l-sm bg-[#2C2A3D]" />
          <span aria-hidden className="absolute -right-[7px] top-[230px] h-[96px] w-[3px] rounded-r-sm bg-[#2C2A3D]" />

          <div className={cn("relative h-full w-full overflow-hidden rounded-[48px]", screen)}>
            <div aria-hidden className="relative flex items-center justify-between px-9 text-[15px] font-semibold" style={{ height: STATUS }}>
              <span className="num pt-1">9:41</span>
              <span className="absolute left-1/2 top-[11px] h-[33px] w-[118px] -translate-x-1/2 rounded-full bg-black" />
              <span className="flex items-center gap-1.5 pt-1">
                <Signal className="size-4" strokeWidth={2.5} />
                <Wifi className="size-4" strokeWidth={2.5} />
                <BatteryFull className="size-5" strokeWidth={2} />
              </span>
            </div>
            <iframe
              ref={frameRef}
              src={src}
              title={title}
              onLoad={onLoad}
              className={cn("block w-full border-0 bg-transparent transition-opacity motion-reduce:transition-none", loaded ? "opacity-100" : "opacity-0")}
              style={{ height: PHONE.height - STATUS - HOME }}
            />
            {!loaded && (
              <div aria-hidden className="absolute inset-x-6 space-y-3" style={{ top: STATUS + 16 }}>
                <div className="skeleton h-8 w-40 rounded-lg" />
                <div className="skeleton h-72 rounded-3xl" />
                <div className="skeleton h-24 rounded-2xl" />
              </div>
            )}
            <div aria-hidden className="flex items-center justify-center" style={{ height: HOME }}>
              <span className="h-[5px] w-[134px] rounded-full bg-current opacity-80" />
            </div>
          </div>
        </div>
      </div>
      {label && <figcaption className="mt-3 text-center text-sm text-fg-2">{label}</figcaption>}
    </figure>
  );
}

/** A browser window that renders the app at desktop width (1280px) and scales it to fit. */
export function BrowserFrame({
  src,
  title,
  url,
  height,
  frameRef,
  className,
}: {
  src: string;
  title: string;
  url: string;
  height: number;
  frameRef?: RefObject<HTMLIFrameElement | null>;
  className?: string;
}) {
  const DESKTOP = 1280;
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(DESKTOP);
  const [loaded, onLoad] = useLoaded(src);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);
  const scale = width > 0 ? Math.min(1, width / DESKTOP) : 1;
  const chrome = 44;
  return (
    <figure
      className={cn(
        "overflow-hidden rounded-2xl border border-white/15 bg-[#F8F7FC] shadow-[0_40px_90px_-30px_rgb(0_0_0/0.75)]",
        className,
      )}
      style={{ height }}
    >
      <div className="flex items-center gap-3 border-b border-[#E4E0EF] bg-[#EFEDF6] px-4 text-[#4A4660]" style={{ height: chrome }}>
        <span aria-hidden className="flex gap-1.5">
          <span className="size-3 rounded-full bg-[#F26D5F]" />
          <span className="size-3 rounded-full bg-[#F4BF4F]" />
          <span className="size-3 rounded-full bg-[#5FC454]" />
        </span>
        <span className="flex h-7 min-w-0 flex-1 items-center gap-1.5 rounded-lg bg-white px-3 text-xs">
          <Lock className="size-3 shrink-0" aria-hidden />
          <span className="truncate">
            <span className="text-[#6B6783]">jodidar.app</span>
            {url}
          </span>
        </span>
      </div>
      <div ref={box} className="relative overflow-hidden" style={{ height: height - chrome }}>
        <iframe
          ref={frameRef}
          src={src}
          title={title}
          onLoad={onLoad}
          className={cn("block origin-top-left border-0 transition-opacity motion-reduce:transition-none", loaded ? "opacity-100" : "opacity-0")}
          style={{ width: DESKTOP, height: (height - chrome) / scale, transform: `scale(${scale})` }}
        />
        {!loaded && (
          <div aria-hidden className="absolute inset-0 grid grid-cols-[180px_1fr] gap-4 p-4">
            <div className="rounded-xl bg-[#ECE9F4]" />
            <div className="space-y-3">
              <div className="h-8 w-1/2 rounded-lg bg-[#ECE9F4]" />
              <div className="h-40 rounded-xl bg-[#ECE9F4]" />
              <div className="h-40 rounded-xl bg-[#ECE9F4]" />
            </div>
          </div>
        )}
      </div>
    </figure>
  );
}
