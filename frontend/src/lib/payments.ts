// Escrow funding. With Razorpay TEST keys the official checkout opens;
// otherwise the API records a simulated payment and the demo carries on.
import { post } from "./api";

interface Order {
  mode: "razorpay-test";
  order_id: string;
  key_id: string;
  amount: number;
}

declare global {
  interface Window {
    Razorpay?: new (opts: Record<string, unknown>) => { open: () => void };
  }
}

function loadCheckout(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Couldn't load Razorpay checkout. Check your connection."));
    document.body.appendChild(s);
  });
}

/** Funds escrow for a deal or a collective. Resolves when funded. */
export async function fundEscrow(path: string, label: string): Promise<void> {
  const res = await post<{ mode: string } & Partial<Order>>(path);
  if (res.mode !== "razorpay-test") return;
  const order = res as Order;
  await loadCheckout();
  await new Promise<void>((resolve, reject) => {
    const rz = new window.Razorpay!({
      key: order.key_id,
      order_id: order.order_id,
      amount: order.amount * 100,
      currency: "INR",
      name: "JodiDar escrow (test mode)",
      description: label,
      handler: async (r: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) => {
        try {
          await post(`${path}/verify`, r);
          resolve();
        } catch (e) {
          reject(e);
        }
      },
      modal: { ondismiss: () => reject(new Error("Payment cancelled")) },
      theme: { color: "#6D28D9" },
    });
    rz.open();
  });
}
