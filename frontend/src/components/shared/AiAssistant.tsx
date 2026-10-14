// DealMeet AI: one assistant window for the Creator Studio and the Brand Console.
// It answers like a person, from the account's own data, and does tasks: drafts run
// straight away, and anything that sends, publishes or pauses waits for Confirm here.
// Backend: ai/assistant.py (/api/assistant/chat).
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowUp, Check, Lightbulb, MessageCircle, Sparkles, SquarePen, Wand2, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { themeClass } from "@/components/ui/overlays";
import { useI18n } from "@/i18n";
import { api, post } from "@/lib/api";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

type Role = "creator" | "brand";

interface ChatActionView {
  tool: string;
  label: string;
  status: "pending" | "done" | "refused" | "cancelled" | "failed" | "expired";
  detail?: string;
  link?: string | null;
  proposal?: { id: string; summary: string; expires_in_s: number };
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  at: string;
  written_by?: "ai" | "template";
  ai_status?: string | null;
  suggestions?: string[];
  action?: ChatActionView | null;
}

interface Conversation {
  id: string;
  messages: ChatMessage[];
}

interface ChatState {
  conversation: Conversation | null;
  starters: string[];
  ai: boolean;
}

const CAN: Record<Role, { icon: typeof MessageCircle; title: string; text: string }[]> = {
  creator: [
    { icon: MessageCircle, title: "Ask about your numbers", text: "Views, your fair price, earnings, deals and brands that fit." },
    { icon: Lightbulb, title: "Get advice", text: "What to post, how to price, how to pitch, in your language." },
    { icon: Wand2, title: "Get things done", text: "Draft pitches, make a plan, save your media kit. Sending waits for your OK." },
  ],
  brand: [
    { icon: MessageCircle, title: "Ask about your campaigns", text: "Applications, shortlists, deals and money in escrow." },
    { icon: Lightbulb, title: "Get advice", text: "Briefs, budgets and choosing creators." },
    { icon: Wand2, title: "Get things done", text: "Draft briefs and offers, publish, pause or send. Each waits for your OK." },
  ],
};

// ------------------------------------------------------------------ one window per shell
const Ctx = createContext<{ open: () => void } | null>(null);

/** Wrap a shell once: it owns the window, and any AiAssistantButton inside opens it. Ctrl/⌘ J toggles it too. */
export function AiAssistantProvider({ role, children }: { role: Role; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "j") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const value = useMemo(() => ({ open: () => setOpen(true) }), []);
  return (
    <Ctx.Provider value={value}>
      {children}
      <AssistantWindow role={role} open={open} onOpenChange={setOpen} />
    </Ctx.Provider>
  );
}

export function AiAssistantButton({ compact = false, className }: { compact?: boolean; className?: string }) {
  const ctx = useContext(Ctx);
  if (compact) {
    return (
      <Button variant="ghost" size="icon-sm" className={className} onClick={() => ctx?.open()} aria-label="Open DealMeet AI assistant">
        <Sparkles className="text-accent" aria-hidden />
      </Button>
    );
  }
  return (
    <button
      type="button"
      onClick={() => ctx?.open()}
      className={cn(
        "group relative isolate flex w-full items-center gap-3 overflow-hidden rounded-2xl border border-line px-3 py-2.5 text-left transition-colors hover:border-line-strong",
        className,
      )}
    >
      <span aria-hidden className="absolute inset-0 -z-10 bg-signature opacity-[0.12] transition-opacity group-hover:opacity-20" />
      <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-signature text-white shadow-[0_6px_18px_-8px_rgb(219_39_119/0.7)]">
        <Sparkles className="size-4 transition-transform duration-300 group-hover:rotate-12" aria-hidden />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-fg">AI assistant</span>
        <span className="block truncate text-xs text-muted">Ask, or get things done</span>
      </span>
    </button>
  );
}

// ------------------------------------------------------------------ the window
function AssistantWindow({ role, open, onOpenChange }: { role: Role; open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const { lang } = useI18n();
  const reduce = useReducedMotion();
  const name = useSession(role).data?.user.name?.split(" ")[0];
  const state = useQuery({ queryKey: ["assistant-chat", role], queryFn: () => api<ChatState>("/assistant/chat"), enabled: open, staleTime: 30_000 });
  const [conv, setConv] = useState<Conversation | null>(null);
  const [fresh, setFresh] = useState<string | null>(null); // the reply to type out
  const [draft, setDraft] = useState("");
  const loaded = useRef(false);
  const scroller = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (state.data && !loaded.current) {
      setConv(state.data.conversation);
      loaded.current = true;
    }
  }, [state.data]);

  const scrollDown = useCallback(() => {
    requestAnimationFrame(() => scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: reduce ? "auto" : "smooth" }));
  }, [reduce]);

  const refreshApp = () => void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "assistant-chat" });

  const send = useMutation({
    mutationFn: (message: string) => post<{ conversation_id: string; messages: ChatMessage[] }>("/assistant/chat", { message, conversation_id: conv?.id ?? null, ui_lang: lang }),
    onMutate: (message) => {
      const pending: ChatMessage = { id: `local-${Date.now()}`, role: "user", text: message, at: new Date().toISOString() };
      setConv((c) => ({ id: c?.id ?? "", messages: [...(c?.messages ?? []), pending] }));
      scrollDown();
    },
    onSuccess: (out) => {
      setConv((c) => ({ id: out.conversation_id, messages: [...(c?.messages ?? []).filter((m) => !m.id.startsWith("local-")), ...out.messages] }));
      setFresh(out.messages[1]?.id ?? null);
      if (out.messages[1]?.action?.status === "done") refreshApp();
      void qc.invalidateQueries({ queryKey: ["assistant-chat", role] });
      scrollDown();
    },
    onError: (e) => {
      setConv((c) => (c ? { ...c, messages: c.messages.filter((m) => !m.id.startsWith("local-")) } : c));
      toast.error((e as Error).message);
    },
  });

  const settle = useMutation({
    mutationFn: (v: { proposal: string; decision: "confirm" | "cancel" }) =>
      post<{ conversation: Conversation }>(`/assistant/chat/${conv?.id}/actions/${v.proposal}/${v.decision}`),
    onSuccess: (out, v) => {
      setConv(out.conversation);
      if (v.decision === "confirm") refreshApp();
      scrollDown();
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const submit = (text = draft) => {
    const t = text.trim();
    if (!t || send.isPending) return;
    setDraft("");
    send.mutate(t);
  };

  useEffect(() => {
    if (open) {
      scrollDown();
      setTimeout(() => input.current?.focus(), 60);
    }
  }, [open, scrollDown]);

  const messages = conv?.messages ?? [];
  const last = messages[messages.length - 1];
  const chips = last?.role === "assistant" && !send.isPending ? (last.suggestions?.length ? last.suggestions : []) : [];

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className={cn(themeClass(), "fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px]")} />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className={cn(
            themeClass(),
            "fixed inset-0 z-50 flex flex-col bg-[var(--surface-solid)] text-fg shadow-2xl outline-none sm:inset-y-3 sm:left-auto sm:right-3 sm:w-[440px] sm:rounded-[28px] sm:border sm:border-line-strong",
          )}
        >
          {/* Header */}
          <div className="relative flex items-center gap-3 border-b border-line px-4 py-3 sm:px-5">
            <span aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-px bg-signature opacity-70 sm:rounded-t-[28px]" />
            <span className="relative grid size-9 place-items-center rounded-xl bg-signature text-white">
              <Sparkles className="size-[18px]" aria-hidden />
              <span aria-hidden className={cn("absolute -bottom-0.5 -right-0.5 size-2.5 rounded-full border-2 border-[var(--surface-solid)]", state.data?.ai ? "bg-success" : "bg-muted")} />
            </span>
            <div className="min-w-0 flex-1">
              <DialogPrimitive.Title className="font-display text-[15px] font-semibold leading-tight">DealMeet AI</DialogPrimitive.Title>
              <p className="truncate text-xs text-muted">{state.data && !state.data.ai ? "Quick answers from templates (live AI is off)" : "Knows your data · asks before acting"}</p>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="New chat"
              title="New chat"
              disabled={!messages.length || send.isPending}
              onClick={() => {
                setConv(null);
                setFresh(null);
                input.current?.focus();
              }}
            >
              <SquarePen aria-hidden />
            </Button>
            <DialogPrimitive.Close className="grid size-8 place-items-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg" aria-label="Close">
              <X className="size-4" />
            </DialogPrimitive.Close>
          </div>

          {/* Conversation */}
          <div ref={scroller} className="flex-1 overflow-y-auto overscroll-contain px-4 py-5 sm:px-5" aria-live="polite">
            {!messages.length ? (
              <Welcome role={role} name={name} starters={state.data?.starters ?? []} onPick={(s) => submit(s)} reduce={!!reduce} />
            ) : (
              <ol className="space-y-5">
                {messages.map((m) => (
                  <li key={m.id}>
                    {m.role === "user" ? (
                      <UserBubble text={m.text} reduce={!!reduce} />
                    ) : (
                      <AssistantMessage
                        m={m}
                        typing={m.id === fresh && !reduce}
                        onTyped={() => setFresh(null)}
                        onGrow={scrollDown}
                        onSettle={(proposal, decision) => settle.mutate({ proposal, decision })}
                        settling={settle.isPending}
                        aiOn={!!state.data?.ai}
                      />
                    )}
                  </li>
                ))}
                {send.isPending && (
                  <li>
                    <Thinking />
                  </li>
                )}
              </ol>
            )}
            {chips.length > 0 && !fresh && (
              <div className="mt-4 flex flex-wrap gap-1.5 pl-10">
                {chips.map((s) => (
                  <button key={s} type="button" onClick={() => submit(s)} className="rounded-full border border-line bg-surface px-3 py-1.5 text-xs text-fg-2 transition-colors hover:border-accent/60 hover:text-fg">
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Composer */}
          <form
            className="border-t border-line px-3 pb-[max(12px,env(safe-area-inset-bottom))] pt-3 sm:px-4"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
          >
            <div className="flex items-end gap-2 rounded-2xl border border-line-strong bg-surface px-3 py-2 transition-shadow focus-within:shadow-[0_0_0_3px_rgb(124_58_237/0.25)]">
              <textarea
                ref={input}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    submit();
                  }
                }}
                rows={1}
                maxLength={2000}
                placeholder="Ask anything, or tell me what to do…"
                aria-label="Message DealMeet AI"
                className="max-h-36 min-h-6 flex-1 resize-none bg-transparent py-1 text-[15px] leading-6 outline-none [field-sizing:content] placeholder:text-muted"
              />
              <button
                type="submit"
                disabled={!draft.trim() || send.isPending}
                aria-label="Send"
                className="grid size-8 shrink-0 place-items-center rounded-xl bg-signature-strong text-white transition-opacity disabled:opacity-35"
              >
                <ArrowUp className="size-4" aria-hidden />
              </button>
            </div>
            <p className="mt-2 text-center text-[11px] text-muted">Uses your DealMeet data. Prices come from the fair-price engine. It asks before sending anything.</p>
          </form>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function Welcome({ role, name, starters, onPick, reduce }: { role: Role; name?: string; starters: string[]; onPick: (s: string) => void; reduce: boolean }) {
  return (
    <motion.div initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="pt-2">
      <p className="font-display text-2xl font-semibold tracking-tight">
        <span className="text-gradient">Hi{name ? ` ${name}` : ""}.</span>
      </p>
      <p className="mt-1 text-[15px] text-fg-2">
        I'm DealMeet AI. I know your {role === "creator" ? "numbers" : "campaigns and deals"}, and I can do things for you. This replaces Ask and the old Assistant.
      </p>
      <ul className="mt-5 space-y-2">
        {CAN[role].map(({ icon: Icon, title, text }) => (
          <li key={title} className="flex gap-3 rounded-2xl border border-line bg-surface px-3.5 py-3">
            <Icon className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
            <span>
              <span className="block text-sm font-medium">{title}</span>
              <span className="block text-[13px] leading-snug text-muted">{text}</span>
            </span>
          </li>
        ))}
      </ul>
      {starters.length > 0 && (
        <>
          <p className="mt-6 text-xs font-semibold uppercase tracking-[0.1em] text-muted">Try</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {starters.map((s) => (
              <button key={s} type="button" onClick={() => onPick(s)} className="rounded-full border border-line bg-surface px-3 py-1.5 text-[13px] text-fg-2 transition-colors hover:border-accent/60 hover:text-fg">
                {s}
              </button>
            ))}
          </div>
        </>
      )}
    </motion.div>
  );
}

function UserBubble({ text, reduce }: { text: string; reduce: boolean }) {
  return (
    <motion.div initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }} className="flex justify-end">
      <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-accent px-3.5 py-2 text-[15px] leading-relaxed text-accent-fg">{text}</p>
    </motion.div>
  );
}

function Avatar() {
  return (
    <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-lg bg-signature text-white">
      <Sparkles className="size-3.5" />
    </span>
  );
}

function Thinking() {
  return (
    <div className="flex items-center gap-3" role="status" aria-label="DealMeet AI is thinking">
      <Avatar />
      <span className="flex gap-1 rounded-2xl bg-surface-2 px-3.5 py-3">
        {[0, 1, 2].map((i) => (
          <span key={i} className="size-1.5 animate-bounce rounded-full bg-muted" style={{ animationDelay: `${i * 140}ms` }} />
        ))}
      </span>
    </div>
  );
}

/** Types the newest reply out (about 300 characters a second); instantly with reduced motion. */
function useTypewriter(text: string, on: boolean, onDone: () => void, onGrow: () => void) {
  const [n, setN] = useState(on ? 0 : text.length);
  useEffect(() => {
    if (!on) return;
    let i = 0;
    const id = window.setInterval(() => {
      i = Math.min(text.length, i + 5);
      setN(i);
      if (i % 60 < 5) onGrow();
      if (i >= text.length) {
        window.clearInterval(id);
        onDone();
      }
    }, 16);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [on, text]);
  return on ? text.slice(0, n) : text;
}

function AssistantMessage({
  m,
  typing,
  onTyped,
  onGrow,
  onSettle,
  settling,
  aiOn,
}: {
  m: ChatMessage;
  typing: boolean;
  onTyped: () => void;
  onGrow: () => void;
  onSettle: (proposal: string, decision: "confirm" | "cancel") => void;
  settling: boolean;
  aiOn: boolean;
}) {
  const shown = useTypewriter(m.text, typing, onTyped, onGrow);
  return (
    <div className="flex gap-3">
      <Avatar />
      <div className="min-w-0 flex-1 pt-0.5">
        <RichText text={shown} />
        {!typing && m.action && <ActionCard a={m.action} onSettle={onSettle} settling={settling} />}
        {!typing && m.written_by === "template" && aiOn && m.ai_status && (
          <p className="mt-1.5 text-[11px] text-muted">A quick answer from templates: the AI couldn't answer this one just now.</p>
        )}
      </div>
    </div>
  );
}

/** Paragraphs, "- " lists and **bold**: what the assistant writes. Text only, never HTML. */
function RichText({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/);
  return (
    <div className="space-y-2.5 break-words text-[15px] leading-relaxed text-fg">
      {blocks.map((block, i) => {
        const lines = block.split("\n");
        if (lines.every((l) => /^\s*[-•]\s+/.test(l))) {
          return (
            <ul key={i} className="list-disc space-y-1 pl-5 marker:text-muted">
              {lines.map((l, j) => (
                <li key={j}>
                  <Inline text={l.replace(/^\s*[-•]\s+/, "")} />
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i} className="whitespace-pre-wrap">
            <Inline text={block} />
          </p>
        );
      })}
    </div>
  );
}

function Inline({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("**") && p.endsWith("**") && p.length > 4 ? (
          <strong key={i} className="font-semibold">
            {p.slice(2, -2)}
          </strong>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

const STATUS: Record<ChatActionView["status"], { text: string; tone: string }> = {
  pending: { text: "Waiting for you", tone: "text-warn" },
  done: { text: "Done", tone: "text-success" },
  refused: { text: "Couldn't do it", tone: "text-danger" },
  failed: { text: "Didn't go through", tone: "text-danger" },
  cancelled: { text: "Cancelled", tone: "text-muted" },
  expired: { text: "Expired", tone: "text-muted" },
};

function ActionCard({ a, onSettle, settling }: { a: ChatActionView; onSettle: (proposal: string, decision: "confirm" | "cancel") => void; settling: boolean }) {
  const st = STATUS[a.status] ?? STATUS.done;
  return (
    <div className="mt-3 rounded-2xl border border-line bg-surface p-3.5">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-[13px] font-medium">
          <Wand2 className="size-3.5 text-accent" aria-hidden /> {a.label}
        </p>
        <span className={cn("text-xs font-medium", st.tone)}>{st.text}</span>
      </div>
      {a.proposal && a.status === "pending" && (
        <>
          <p className="mt-2 text-sm text-fg-2">{a.proposal.summary}.</p>
          <div className="mt-3 flex gap-2">
            <Button size="sm" variant="primary" loading={settling} onClick={() => onSettle(a.proposal!.id, "confirm")}>
              <Check aria-hidden /> Confirm
            </Button>
            <Button size="sm" variant="ghost" disabled={settling} onClick={() => onSettle(a.proposal!.id, "cancel")}>
              Cancel
            </Button>
          </div>
          <p className="mt-2 text-[11px] text-muted">Nothing happens until you confirm. This expires in 10 minutes.</p>
        </>
      )}
      {a.detail && a.status !== "pending" && <p className="mt-1.5 text-[13px] text-fg-2">{a.detail}</p>}
      {a.link && (a.status === "done" || a.status === "pending") && (
        <Link to={a.link} className="mt-2 inline-block text-[13px] font-medium text-accent underline-offset-4 hover:underline">
          Open in DealMeet
        </Link>
      )}
    </div>
  );
}
