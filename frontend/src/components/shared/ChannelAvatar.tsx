import { useState } from "react";
import { Avatar } from "@/components/shared/Bits";

/** A channel's own thumbnail, or initials if it can't load. */
export function ChannelAvatar({ src, name, size }: { src: string | null | undefined; name: string; size: number }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) return <Avatar name={name} hue={280} size={size} />;
  return <img src={src} alt="" width={size} height={size} className="shrink-0 rounded-full" referrerPolicy="no-referrer" onError={() => setFailed(true)} />;
}
