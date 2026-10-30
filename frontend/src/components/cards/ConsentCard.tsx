import { CheckCircle2, Hotel, Loader2, Lock, Plane, Timer, TrainFront, XCircle } from "lucide-react";
import { useCallback, useEffect, useState, type ReactElement } from "react";
import { api, type Card } from "../../lib/api";
import { cx, inr } from "../../lib/format";
import PaymentModal, { type Order } from "../PaymentModal";
import { BookingRow } from "./Cards";

const KIND_ICON: Record<string, ReactElement> = {
  flight: <Plane size={15} />,
  train: <TrainFront size={15} />,
  hotel: <Hotel size={15} />,
};

function useCountdown(iso: string) {
  const [left, setLeft] = useState(() => new Date(iso).getTime() - Date.now());
  useEffect(() => {
    const id = setInterval(() => setLeft(new Date(iso).getTime() - Date.now()), 1000);
    return () => clearInterval(id);
  }, [iso]);
  return Math.max(0, left);
}

/** The consent gate: nothing is booked until the user approves here and the payment is verified. */
export default function ConsentCard({ card: initial }: { card: Card }) {
  const [card, setCard] = useState(initial);
  const [order, setOrder] = useState<Order | null>(null);
  const [bookings, setBookings] = useState<Card[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmReject, setConfirmReject] = useState(false);
  const [error, setError] = useState("");
  const left = useCountdown(card.hold_expires_at);

  // Saved chat cards can be stale: always show the live status.
  useEffect(() => {
    api<Card>(`/api/consents/${initial.consent_id}`).then(setCard).catch(() => undefined);
  }, [initial.consent_id]);

  const open = card.status === "pending" || card.status === "awaiting_payment";
  const expired = open && left === 0;

  const approve = async () => {
    setBusy(true);
    setError("");
    try {
      setOrder(await api<Order>(`/api/consents/${card.consent_id}/approve`, { method: "POST" }));
    } catch (e) {
      setError((e as Error).message);
      api<Card>(`/api/consents/${card.consent_id}`).then(setCard).catch(() => undefined);
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    setBusy(true);
    try {
      setCard(await api<Card>(`/api/consents/${card.consent_id}/reject`, { method: "POST" }));
    } finally {
      setBusy(false);
      setConfirmReject(false);
    }
  };

  const onPaid = useCallback((b: Card[]) => {
    setOrder(null);
    setBookings(b);
    setCard((c) => ({ ...c, status: "paid" }));
  }, []);
  const onClose = useCallback(() => setOrder(null), []);

  const mm = String(Math.floor(left / 60000)).padStart(2, "0");
  const ss = String(Math.floor((left % 60000) / 1000)).padStart(2, "0");

  return (
    <div className="ticket animate-rise border-2 border-ink-950">
      <div className="flex items-center justify-between gap-3 bg-mustard-500 px-5 py-3">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-widest text-ink-800">Approval needed</div>
          <div className="font-display text-lg font-bold text-ink-950">{card.title}</div>
        </div>
        {open && !expired && (
          <div className="flex items-center gap-1.5 rounded-full bg-ink-950 px-3 py-1 font-mono text-sm font-semibold text-mustard-400" aria-label="Price hold time left">
            <Timer size={14} /> {mm}:{ss}
          </div>
        )}
      </div>

      <div className="space-y-2 px-5 py-4">
        {card.items.map((it: Card, i: number) => (
          <div key={i} className="flex items-start gap-3">
            <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-ink-950 text-mustard-400">{KIND_ICON[it.kind]}</span>
            <div className="flex-1">
              <div className="text-sm font-semibold">{it.title}</div>
              <div className="text-[12px] text-ink-500">{it.terms}</div>
            </div>
            <div className="font-semibold">{inr(it.price_inr)}</div>
          </div>
        ))}
      </div>

      <div className="perforation mx-5" />

      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-500">Total</div>
          <div className="font-display text-2xl font-extrabold">{inr(card.total_inr)}</div>
        </div>

        {open && !expired && (
          <div className="flex items-center gap-2">
            {confirmReject ? (
              <>
                <span className="text-xs text-ink-500">Cancel this request?</span>
                <button className="btn-ghost px-3 py-1.5" onClick={() => setConfirmReject(false)}>Keep</button>
                <button className="btn-dark px-3 py-1.5" onClick={reject} disabled={busy}>Yes, cancel</button>
              </>
            ) : (
              <>
                <button className="btn-ghost" onClick={() => setConfirmReject(true)} disabled={busy}>Cancel</button>
                <button className="btn-dark" onClick={approve} disabled={busy}>
                  {busy ? <Loader2 size={16} className="animate-spin" /> : <Lock size={15} />} Approve & Pay
                </button>
              </>
            )}
          </div>
        )}
        {(expired || card.status === "expired") && <span className="flex items-center gap-1.5 text-sm font-semibold text-ink-500"><Timer size={16} /> Price hold expired — ask Sara to search again</span>}
        {card.status === "rejected" && <span className="flex items-center gap-1.5 text-sm font-semibold text-ink-500"><XCircle size={16} /> Cancelled by you</span>}
        {card.status === "paid" && <span className="flex items-center gap-1.5 text-sm font-semibold text-emerald-700"><CheckCircle2 size={16} /> Approved & paid</span>}
      </div>

      {error && <p className="mx-5 mb-4 rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}

      {bookings && (
        <div className={cx("space-y-2 border-t border-ink-100 bg-cream px-5 py-4")}>
          <div className="text-sm font-semibold text-emerald-700">Booked! Your references:</div>
          {bookings.map((b) => <BookingRow key={b.id} b={b} />)}
        </div>
      )}

      {order && <PaymentModal order={order} onClose={onClose} onPaid={onPaid} />}
    </div>
  );
}
