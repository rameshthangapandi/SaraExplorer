import { CheckCircle2, Copy, Loader2, Lock, ShieldCheck, Smartphone, X } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { api, type Card } from "../lib/api";
import { cx, inr } from "../lib/format";

export type Order = {
  provider: "upi" | "razorpay" | "mock";
  order_id?: string;
  amount_paise: number;
  currency: string;
  key_id?: string | null;
  name: string;
  description: string;
  prefill: { name: string; email: string };
  hold_expires_at: string;
  payments?: VendorPay[];
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

export type VendorPay = {
  order_id: string;
  amount_inr: number;
  status: string;
  utr: string | null;
  upi_uri?: string;
  vendor: { name: string; kind: string; upi_id: string; pending: boolean };
};

function VendorQr({ p }: { p: VendorPay }) {
  const [qr, setQr] = useState("");
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (p.upi_uri) QRCode.toDataURL(p.upi_uri, { width: 240, margin: 1, color: { dark: "#0b0b0b", light: "#ffffff" } }).then(setQr);
  }, [p.upi_uri]);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(p.vendor.upi_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked */
    }
  };
  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl border border-ink-100 bg-cream p-4">
      <div className="relative">
        {qr ? <img src={qr} alt={`UPI QR code to pay ${inr(p.amount_inr)} to ${p.vendor.name}`} className="size-48 rounded-xl bg-white p-2" /> : <Loader2 className="animate-spin" />}
      </div>
      <div className="text-center text-sm">
        <div className="font-semibold">{p.vendor.name}</div>
        <button onClick={copy} className="mt-0.5 inline-flex items-center gap-1 font-mono text-xs text-ink-600 hover:text-ink-950">
          {p.vendor.upi_id} {copied ? <CheckCircle2 size={12} className="text-emerald-600" /> : <Copy size={12} />}
        </button>
      </div>
    </div>
  );
}

function UpiPayment({ order, onClose, onSubmitted }: Props) {
  const [payments, setPayments] = useState<VendorPay[]>(order.payments ?? []);
  const [index, setIndex] = useState(() => Math.max(0, (order.payments ?? []).findIndex((p) => p.status === "created")));
  const [utr, setUtr] = useState("");
  const [enterUtr, setEnterUtr] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const isMobile = /Android|iPhone|iPad/i.test(navigator.userAgent);
  const p = payments[index];
  const pendingCount = payments.filter((x) => x.status === "created").length;

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await api<{ consent: Card; payments: VendorPay[] }>("/api/payments/upi/submit", { method: "POST", body: { order_id: p.order_id, utr } });
      setPayments(res.payments);
      setUtr("");
      setEnterUtr(false);
      const next = res.payments.findIndex((x) => x.status === "created");
      if (next === -1) onSubmitted(res.consent);
      else setIndex(next);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!p) return null;
  const validUtr = /^\d{12}$/.test(utr.replace(/\s/g, ""));

  return (
    <Shell onClose={onClose} busy={busy} title="Pay vendors with UPI">
      <div className="bg-ink-950 px-6 py-5 text-cream">
        <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-mustard-400"><Lock size={12} /> Pay vendors directly · UPI</div>
        <div className="mt-1 font-display text-3xl font-extrabold">{inr(p.amount_inr)}</div>
        <p className="text-xs text-ink-300">to {p.vendor.name} · payment {index + 1} of {payments.length}</p>
        {payments.length > 1 && (
          <div className="mt-3 flex gap-1.5">
            {payments.map((x, i) => (
              <button key={x.order_id} onClick={() => x.status === "created" && (setIndex(i), setEnterUtr(false))}
                className={cx("h-1.5 flex-1 rounded-full", x.status !== "created" ? "bg-emerald-400" : i === index ? "bg-mustard-400" : "bg-ink-600")}
                aria-label={`${x.vendor.name}: ${x.status === "created" ? "to pay" : "submitted"}`} />
            ))}
          </div>
        )}
      </div>

      <div className="space-y-4 p-6">
        {!enterUtr ? (
          <>
            <p className="text-sm text-ink-600">
              {isMobile ? "Tap “Open UPI app”" : "Scan with any UPI app"}, check the amount is <b className="text-ink-950">{inr(p.amount_inr)}</b> and that it goes to <b className="text-ink-950">{p.vendor.name}</b>, then pay.
            </p>
            <VendorQr p={p} />
            <a href={p.upi_uri} className="btn-outline w-full"><Smartphone size={16} /> Open UPI app</a>
            <button onClick={() => setEnterUtr(true)} className="btn-dark w-full py-3">I've paid {p.vendor.name} — enter UTR</button>
          </>
        ) : (
          <>
            <div>
              <label className="label" htmlFor="utr">UPI reference number (UTR) for {p.vendor.name}</label>
              <input id="utr" className="input font-mono tracking-widest" inputMode="numeric" maxLength={14} autoFocus
                placeholder="12-digit number" value={utr} onChange={(e) => setUtr(e.target.value.replace(/[^\d ]/g, ""))} />
              <p className="mt-1.5 text-xs text-ink-500">Find it in your UPI app under the payment details (UPI Ref No. / Transaction ID).</p>
            </div>
            {error && <p role="alert" className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
            <button onClick={submit} disabled={!validUtr || busy} className="btn-primary w-full py-3">
              {busy && <Loader2 size={16} className="animate-spin" />}
              {pendingCount > 1 ? "Submit & pay next vendor" : "Submit for vendor confirmation"}
            </button>
            <button onClick={() => setEnterUtr(false)} className="btn-ghost w-full">Back to QR</button>
          </>
        )}
        <p className="flex items-start gap-1.5 text-[11px] leading-relaxed text-ink-400">
          <ShieldCheck size={13} className="mt-0.5 shrink-0" />
          You pay each vendor directly — Sara Explorer never holds your money. Each part of your trip is booked once its vendor confirms receipt. Never share your UPI PIN.
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
