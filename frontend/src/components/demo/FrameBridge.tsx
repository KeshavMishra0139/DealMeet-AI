// The bridge between the guided demo pages and copies of the app running inside their frames.
import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { postToParent, type FrameMessage } from "@/lib/phone";

/** Listens for DealMeet messages from same-origin frames; the handler gets the sending window to tell frames apart. */
export function useFrameMessages(handler: (msg: FrameMessage, source: MessageEventSource | null) => void) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.origin !== window.location.origin || typeof e.data?.type !== "string" || !e.data.type.startsWith("jd:")) return;
      ref.current(e.data as FrameMessage, e.source);
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);
}

/** Runs inside framed copies of the app: follows navigation requests and reports the route. */
export function EmbedBridge() {
  const location = useLocation();
  const navigate = useNavigate();
  useFrameMessages((msg, source) => {
    if (source !== window.parent) return;
    if (msg.type === "jd:navigate") navigate(msg.to);
  });
  useEffect(() => {
    postToParent({ type: "jd:route", path: `${location.pathname}${location.search}${location.hash}` });
  }, [location]);
  return null;
}
