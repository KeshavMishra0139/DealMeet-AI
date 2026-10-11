// Motion primitives shared by the Creator Studio, the Brand Console and the demo
// screens. Every effect checks reduced motion first and falls back to a plain,
// fully readable layout; nothing here hides content from assistive tech.
import {
  animate,
  motion,
  useInView,
  useMotionTemplate,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  type HTMLMotionProps,
  type Variants,
} from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

export const EASE = [0.22, 1, 0.36, 1] as const;

const rise: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE } },
};

/** Fades and lifts its children in the first time they scroll into view. */
export function Reveal({
  children,
  delay = 0,
  className,
  as = "div",
  ...rest
}: { children: ReactNode; delay?: number; className?: string; as?: "div" | "section" | "li" } & Omit<HTMLMotionProps<"div">, "children">) {
  const reduce = useReducedMotion();
  const Comp = motion[as] as typeof motion.div;
  if (reduce) {
    return (
      <Comp className={className} {...rest}>
        {children}
      </Comp>
    );
  }
  return (
    <Comp
      className={className}
      initial="hidden"
      whileInView="show"
      // No inset on the bottom edge: content in the last few pixels of a page (the landing
      // footer) could never cross an inset line, so it stayed invisible.
      viewport={{ once: true, amount: 0.15 }}
      variants={delay ? { hidden: rise.hidden, show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE, delay } } } : rise}
      {...rest}
    >
      {children}
    </Comp>
  );
}

/** Staggers <StaggerItem> children as the group scrolls into view. */
export function Stagger({ children, className, gap = 0.07, as = "div" }: { children: ReactNode; className?: string; gap?: number; as?: "div" | "ul" | "ol" | "dl" }) {
  const reduce = useReducedMotion();
  const Comp = motion[as] as typeof motion.div;
  if (reduce) {
    const Plain = as;
    return <Plain className={className}>{children}</Plain>;
  }
  return (
    <Comp
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, amount: 0.1 }}
      variants={{ hidden: {}, show: { transition: { staggerChildren: gap } } }}
    >
      {children}
    </Comp>
  );
}

export function StaggerItem({ children, className, as = "div" }: { children: ReactNode; className?: string; as?: "div" | "li" }) {
  const Comp = motion[as] as typeof motion.div;
  return (
    <Comp className={className} variants={rise}>
      {children}
    </Comp>
  );
}

/**
 * A card that tilts in 3D toward the pointer, with a soft glare that follows it.
 * Mouse and pen only: touch scrolling never tilts, and reduced motion turns it off.
 */
export function TiltCard({
  children,
  className,
  max = 7,
  glare = true,
}: {
  children: ReactNode;
  className?: string;
  max?: number;
  glare?: boolean;
}) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);
  const spring = { stiffness: 220, damping: 22, mass: 0.6 };
  const rx = useSpring(useTransform(py, [0, 1], [max, -max]), spring);
  const ry = useSpring(useTransform(px, [0, 1], [-max, max]), spring);
  const gx = useTransform(px, (v) => `${v * 100}%`);
  const gy = useTransform(py, (v) => `${v * 100}%`);
  const glareBg = useMotionTemplate`radial-gradient(420px circle at ${gx} ${gy}, rgb(255 255 255 / 0.16), transparent 45%)`;
  const [hover, setHover] = useState(false);

  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div
      ref={ref}
      className={cn("relative [transform-style:preserve-3d]", className)}
      style={{ rotateX: rx, rotateY: ry, transformPerspective: 900 }}
      onPointerMove={(e) => {
        if (e.pointerType === "touch" || !ref.current) return;
        const r = ref.current.getBoundingClientRect();
        px.set((e.clientX - r.left) / r.width);
        py.set((e.clientY - r.top) / r.height);
        if (!hover) setHover(true);
      }}
      onPointerLeave={() => {
        px.set(0.5);
        py.set(0.5);
        setHover(false);
      }}
    >
      {children}
      {glare && (
        <motion.span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-[inherit] mix-blend-soft-light transition-opacity duration-300"
          style={{ background: glareBg, opacity: hover ? 1 : 0 }}
        />
      )}
    </motion.div>
  );
}

/**
 * Counts a number up when it scrolls into view. Screen readers get the final value
 * straight away; the animated digits are hidden from them.
 */
export function CountUp({ value, format, className, duration = 1.1 }: { value: number; format: (n: number) => string; className?: string; duration?: number }) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const seen = useInView(ref, { once: true, amount: 0.6 });
  const [shown, setShown] = useState(reduce ? value : 0);
  useEffect(() => {
    if (reduce) {
      setShown(value);
      return;
    }
    if (!seen) return;
    const controls = animate(0, value, { duration, ease: EASE, onUpdate: (v) => setShown(v) });
    return () => controls.stop();
  }, [seen, value, reduce, duration]);
  return (
    <span className={className}>
      <span className="sr-only">{format(value)}</span>
      <span ref={ref} aria-hidden>
        {format(Math.round(shown))}
      </span>
    </span>
  );
}

/** A thin signature-gradient bar showing how far down the page you are. */
export function ScrollProgress({ className }: { className?: string }) {
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 140, damping: 30, mass: 0.4 });
  if (reduce) return null;
  return (
    <motion.div
      aria-hidden
      className={cn("pointer-events-none fixed inset-x-0 top-0 z-40 h-[3px] origin-left bg-signature", className)}
      style={{ scaleX }}
    />
  );
}

/** The aurora background, drifting a little slower than the page as you scroll. */
export function ParallaxAurora() {
  const reduce = useReducedMotion();
  const { scrollY } = useScroll();
  const y = useTransform(scrollY, [0, 2000], [0, -180]);
  const rotate = useTransform(scrollY, [0, 2000], [0, 8]);
  return (
    <motion.div className="aurora" aria-hidden style={reduce ? undefined : { y, rotate }}>
      <span />
    </motion.div>
  );
}

/** Each new screen eases in; keyed by path so it runs on every navigation. */
export function PageFade({ children, className }: { children: ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  const { pathname } = useLocation();
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div
      key={pathname}
      className={className}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}
