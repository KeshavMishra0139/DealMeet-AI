import QRCode from "qrcode";
import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

/** A QR code drawn in the browser (no outside QR service), with a PNG download. */
export function QrCode({ url, label, size = 168, fileName = "dealmeet-qr.png" }: { url: string; label: string; size?: number; fileName?: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    QRCode.toDataURL(url, { margin: 1, width: size * 2, errorCorrectionLevel: "M", color: { dark: "#16132B", light: "#FFFFFF" } })
      .then((d) => live && setSrc(d))
      .catch(() => live && setSrc(null));
    return () => {
      live = false;
    };
  }, [url, size]);
  if (!src) return <div className="rounded-xl bg-white" style={{ width: size, height: size }} aria-hidden />;
  return (
    <figure className="flex flex-col items-center gap-2">
      <img src={src} width={size} height={size} alt={label} className="rounded-xl bg-white p-1.5" />
      <Button asChild size="sm" variant="ghost">
        <a href={src} download={fileName}>
          <Download aria-hidden /> Download QR
        </a>
      </Button>
    </figure>
  );
}
