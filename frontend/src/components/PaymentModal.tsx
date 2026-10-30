import { CheckCircle2, Copy, Loader2, Lock, ShieldCheck, Smartphone, X } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { api, type Card } from "../lib/api";
import { inr } from "../lib/format";

export type Order = {
  provider: "upi" | "razorpay" | "mock";
  order_id: string;
  amount_paise: number;
  currency: string;
  key_id: string | null;
  name: string;
  description: string;
  prefill: { name: string; email: string };
  hold_expires_at: string;
  upi_uri?: string;
  payee_upi_id?: string;
  payee_name?: string;
};

type Props = {
  order: Order;
  onClose: () => void;
  /** Payment confirmed by a gateway signature (razorpay) — bookings exist. */
  onPaid: (bookings: Card[]) => void;
  /** UPI payment submitted for verification — NOT booked yet. */
  onSubmitted: (consent: Card) => void;
};

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

function Shell({ children, onClose, busy, title }: { children: ReactNode; onClose: () => void; busy: boolean; title: string }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);
  // Portal to <body> so the dialog isn't clipped by the consent card's mask / transform.
  return createPortal(
    <div className="fixed inset-0 z-[1000] grid place-items-center overflow-y-auto bg-ink-950/60 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={title}>
      <div className="relative my-auto w-full max-w-md animate-rise overflow-hidden rounded-3xl bg-white shadow-2xl">
        <button onClick={onClose} disabled={busy} className="absolute right-3 top-3 z-10 rounded-full p-1.5 text-ink-300 hover:bg-ink-800 hover:text-cream" aria-label="Close">
          <X size={18} />
        </button>
        {children}
      </div>
    </div>,
    document.body,
  );
}

function UpiPayment({ order, onClose, onSubmitted }: Props) {
  const [qr, setQr] = useState("");
  const [utr, setUtr] = useState("");
  const [paidClicked, setPaidClicked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const amount = order.amount_paise / 100;
  const isMobile = /Android|iPhone|iPad/i.test(navigator.userAgent);

  useEffect(() => {
    if (order.upi_uri) QRCode.toDataURL(order.upi_uri, { width: 260, margin: 1, color: { dark: "#0b0b0b", light: "#ffffff" } }).then(setQr);
  }, [order.upi_uri]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(order.payee_upi_id ?? "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked */
    }
  };

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      onSubmitted(await api<Card>("/api/payments/upi/submit", { method: "POST", body: { order_id: order.order_id, utr } }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const validUtr = /^\d{12}$/.test(utr.replace(/\s/g, ""));

  return (
    <Shell onClose={onClose} busy={busy} title="Pay with UPI">
      <div className="bg-ink-950 px-6 py-5 text-cream">
        <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-mustard-400"><Lock size={12} /> Secure UPI payment</div>
        <div className="mt-1 font-display text-3xl font-extrabold">{inr(amount)}</div>
        <p className="text-xs text-ink-300">{order.description} · Ref {order.order_id}</p>
      </div>

      <div className="space-y-4 p-6">
        {!paidClicked ? (
          <>
            <ol className="space-y-1 text-sm text-ink-600">
              <li><b className="text-ink-950">1.</b> {isMobile ? "Tap “Open UPI app”" : "Scan the QR with any UPI app"} (GPay, PhonePe, Paytm, BHIM…)</li>
              <li><b className="text-ink-950">2.</b> Check the amount is <b className="text-ink-950">{inr(amount)}</b> and pay</li>
              <li><b className="text-ink-950">3.</b> Come back and enter the 12-digit UPI reference (UTR)</li>
            </ol>
            <div className="flex flex-col items-center gap-3 rounded-2xl border border-ink-100 bg-cream p-4">
              {qr ? <img src={qr} alt={`UPI QR code to pay ${inr(amount)}`} className="size-52 rounded-xl bg-white p-2" /> : <Loader2 className="animate-spin" />}
              <div className="text-center text-sm">
                <div className="font-semibold">{order.payee_name}</div>
                <button onClick={copy} className="mt-0.5 inline-flex items-center gap-1 font-mono text-xs text-ink-600 hover:text-ink-950">
                  {order.payee_upi_id} {copied ? <CheckCircle2 size={12} className="text-emerald-600" /> : <Copy size={12} />}
                </button>
              </div>
            </div>
            <a href={order.upi_uri} className="btn-outline w-full"><Smartphone size={16} /> Open UPI app</a>
            <button onClick={() => setPaidClicked(true)} className="btn-dark w-full py-3">I've paid — enter UTR</button>
          </>
        ) : (
          <>
            <div>
              <label className="label" htmlFor="utr">UPI reference number (UTR)</label>
              <input id="utr" className="input font-mono tracking-widest" inputMode="numeric" maxLength={14} autoFocus
                placeholder="12-digit number" value={utr} onChange={(e) => setUtr(e.target.value.replace(/[^\d ]/g, ""))} />
              <p className="mt-1.5 text-xs text-ink-500">Find it in your UPI app under the payment details (also called UPI Ref No. / Transaction ID).</p>
            </div>
            {error && <p role="alert" className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
            <button onClick={submit} disabled={!validUtr || busy} className="btn-primary w-full py-3">
              {busy && <Loader2 size={16} className="animate-spin" />} Submit payment for verification
            </button>
            <button onClick={() => setPaidClicked(false)} className="btn-ghost w-full">Back to QR</button>
          </>
        )}
        <p className="flex items-start gap-1.5 text-[11px] leading-relaxed text-ink-400">
          <ShieldCheck size={13} className="mt-0.5 shrink-0" />
          Your trip is booked only after we confirm the money has been received. Never share your UPI PIN with anyone.
        </p>
      </div>
    </Shell>
  );
}

function RazorpayPayment({ order, onClose, onPaid }: Props) {
  const [error, setError] = useState("");
  useEffect(() => {
    loadRazorpay()
      .then(() => {
        new window.Razorpay({
          key: order.key_id, amount: order.amount_paise, currency: order.currency, order_id: order.order_id,
          name: order.name, description: order.description, prefill: order.prefill, theme: { color: "#e3a812" },
          handler: async (r: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) => {
            try {
              const res = await api<{ bookings: Card[] }>("/api/payments/verify", {
                method: "POST", body: { order_id: r.razorpay_order_id, payment_id: r.razorpay_payment_id, signature: r.razorpay_signature },
              });
              onPaid(res.bookings);
            } catch (e) {
              setError((e as Error).message);
            }
          },
          modal: { ondismiss: onClose },
        }).open();
      })
      .catch((e) => setError(e.message));
  }, [order, onClose, onPaid]);
  return error ? <div className="fixed inset-x-0 bottom-6 z-[1000] mx-auto w-fit rounded-xl bg-red-600 px-4 py-2 text-sm text-white">{error}</div> : null;
}

export default function PaymentModal(props: Props) {
  if (props.order.provider === "upi") return <UpiPayment {...props} />;
  if (props.order.provider === "razorpay") return <RazorpayPayment {...props} />;
  return (
    <Shell onClose={props.onClose} busy={false} title="Payments unavailable">
      <div className="p-6 text-sm text-ink-600">Online payments are not configured. Please contact support.</div>
    </Shell>
  );
}
