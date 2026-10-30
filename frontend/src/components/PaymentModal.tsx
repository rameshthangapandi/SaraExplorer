import { CreditCard, Loader2, Lock, ShieldCheck, Smartphone, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api, type Card } from "../lib/api";
import { cx, inr } from "../lib/format";

export type Order = {
  provider: "mock" | "razorpay";
  order_id: string;
  amount_paise: number;
  currency: string;
  key_id: string | null;
  name: string;
  description: string;
  prefill: { name: string; email: string };
};

type Props = { order: Order; onClose: () => void; onPaid: (bookings: Card[]) => void };

declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    Razorpay?: any;
  }
}

function loadRazorpay(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.Razorpay) return resolve();
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Could not load Razorpay"));
    document.body.appendChild(s);
  });
}

async function verify(order_id: string, payment_id: string, signature: string) {
  return api<{ bookings: Card[] }>("/api/payments/verify", { method: "POST", body: { order_id, payment_id, signature } });
}

export default function PaymentModal({ order, onClose, onPaid }: Props) {
  const [method, setMethod] = useState<"upi" | "card">("upi");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const amount = order.amount_paise / 100;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  // Real Razorpay Checkout: card/UPI details are entered on Razorpay's side, never on our servers.
  useEffect(() => {
    if (order.provider !== "razorpay") return;
    loadRazorpay()
      .then(() => {
        const rzp = new window.Razorpay({
          key: order.key_id, amount: order.amount_paise, currency: order.currency, order_id: order.order_id,
          name: order.name, description: order.description, prefill: order.prefill, theme: { color: "#e3a812" },
          handler: async (r: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) => {
            try {
              const res = await verify(r.razorpay_order_id, r.razorpay_payment_id, r.razorpay_signature);
              onPaid(res.bookings);
            } catch (e) {
              setError((e as Error).message);
            }
          },
          modal: { ondismiss: onClose },
        });
        rzp.open();
      })
      .catch((e) => setError(e.message));
  }, [order, onClose, onPaid]);

  if (order.provider === "razorpay") {
    return error ? <div className="fixed inset-x-0 bottom-6 mx-auto w-fit rounded-xl bg-red-600 px-4 py-2 text-sm text-white">{error}</div> : null;
  }

  const pay = async () => {
    setBusy(true);
    setError("");
    try {
      // The test gateway signs the payment server-side exactly like a real gateway; we then verify it.
      const p = await api<{ payment_id: string; signature: string }>("/api/payments/mock/pay", { method: "POST", body: { order_id: order.order_id } });
      const res = await verify(order.order_id, p.payment_id, p.signature);
      onPaid(res.bookings);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  // Portal to <body> so the dialog isn't clipped by the consent card's mask / transform.
  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink-950/60 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="pay-title">
      <div className="w-full max-w-sm animate-rise overflow-hidden rounded-3xl bg-white shadow-2xl">
        <div className="flex items-start justify-between bg-ink-950 px-5 py-4 text-cream">
          <div>
            <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-mustard-400"><Lock size={12} /> Secure checkout</div>
            <h2 id="pay-title" className="mt-1 text-lg font-bold">Sara Pay</h2>
            <p className="text-xs text-ink-300">{order.description}</p>
          </div>
          <button onClick={onClose} disabled={busy} className="rounded-full p-1 text-ink-300 hover:bg-ink-800 hover:text-cream" aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="space-y-4 p-5">
          <div className="rounded-2xl bg-mustard-50 p-4 text-center">
            <div className="text-xs font-semibold uppercase tracking-wider text-mustard-800">Amount to pay</div>
            <div className="font-display text-3xl font-extrabold">{inr(amount)}</div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {([["upi", "UPI", <Smartphone size={16} key="u" />], ["card", "Card", <CreditCard size={16} key="c" />]] as const).map(([id, label, icon]) => (
              <button key={id} onClick={() => setMethod(id)}
                className={cx("flex items-center justify-center gap-2 rounded-xl border-2 py-3 text-sm font-semibold transition",
                  method === id ? "border-ink-950 bg-ink-950 text-cream" : "border-ink-100 hover:border-ink-300")}>
                {icon} {label}
              </button>
            ))}
          </div>
          <p className="rounded-xl border border-dashed border-mustard-300 bg-mustard-50/50 p-3 text-xs leading-relaxed text-mustard-800">
            <strong>Test mode.</strong> This is Sara Explorer's built-in test gateway — no money is charged and no card or UPI details are collected.
          </p>
          {error && <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
          <button onClick={pay} disabled={busy} className="btn-primary w-full py-3 text-base">
            {busy ? <Loader2 size={18} className="animate-spin" /> : <Lock size={16} />} Pay {inr(amount)}
          </button>
          <p className="flex items-center justify-center gap-1.5 text-[11px] text-ink-400"><ShieldCheck size={12} /> Signed & verified server-side · amount locked by your approval</p>
        </div>
      </div>
    </div>,
    document.body,
  );
}
