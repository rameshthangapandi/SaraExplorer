import { Loader2, Ticket } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BookingRow } from "../components/cards/Cards";
import ConsentCard from "../components/cards/ConsentCard";
import { api, type Card } from "../lib/api";
import { inr } from "../lib/format";
import { PageHeader } from "./Strategist";

function CancelButton({ b, onDone }: { b: Card; onDone: (b: Card) => void }) {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  if (b.status === "cancelled") return null;
  if (!confirm) return <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => setConfirm(true)}>Cancel</button>;
  return (
    <span className="flex items-center gap-1">
      <button className="btn-ghost px-3 py-1.5 text-xs" onClick={() => setConfirm(false)}>Keep</button>
      <button className="btn-dark px-3 py-1.5 text-xs" disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            onDone(await api<Card>(`/api/bookings/${b.id}/cancel`, { method: "POST" }));
          } finally {
            setBusy(false);
          }
        }}>
        {busy && <Loader2 size={12} className="animate-spin" />} Confirm cancel
      </button>
    </span>
  );
}

export default function Trips() {
  const [items, setItems] = useState<Card[] | null>(null);
  const [pending, setPending] = useState<Card[]>([]);

  useEffect(() => {
    api<Card[]>("/api/bookings").then(setItems).catch(() => setItems([]));
    api<Card[]>("/api/consents").then(setPending).catch(() => setPending([]));
  }, []);

  const active = items?.filter((b) => b.status !== "cancelled") ?? [];
  const total = active.reduce((s, b) => s + b.amount_inr, 0);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <PageHeader title="My Trips" text="Approvals in progress, payments being verified, and every confirmed booking." />

      {pending.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-bold">In progress</h2>
          <div className="space-y-4">{pending.map((c) => <ConsentCard key={c.consent_id} card={c} />)}</div>
        </section>
      )}

      <h2 className="mb-3 text-lg font-bold">Booked</h2>
      {items === null ? (
        <Loader2 className="animate-spin text-mustard-600" />
      ) : items.length === 0 ? (
        <div className="card p-10 text-center">
          <Ticket className="mx-auto text-mustard-500" size={40} />
          <h3 className="mt-3 text-xl font-bold">No confirmed bookings yet</h3>
          <p className="mt-1 text-sm text-ink-500">Bookings appear here once your payment is confirmed.</p>
          <Link to="/app" className="btn-primary mt-5">Plan a trip</Link>
        </div>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-3">
            <div className="rounded-2xl bg-ink-950 px-5 py-3 text-cream"><div className="text-xs text-ink-400">Active bookings</div><div className="font-display text-2xl font-bold text-mustard-400">{active.length}</div></div>
            <div className="rounded-2xl bg-ink-950 px-5 py-3 text-cream"><div className="text-xs text-ink-400">Total paid</div><div className="font-display text-2xl font-bold text-mustard-400">{inr(total)}</div></div>
          </div>
          <div className="space-y-3">
            {items.map((b) => (
              <BookingRow key={b.id} b={b} action={<CancelButton b={b} onDone={(nb) => setItems((all) => all!.map((x) => (x.id === nb.id ? nb : x)))} />} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
