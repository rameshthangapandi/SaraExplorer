import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type Card } from "../lib/api";
import { cx, inr } from "../lib/format";
import { PageHeader } from "./Strategist";

const TABS = [
  { id: "submitted", label: "To verify" },
  { id: "paid", label: "Confirmed" },
  { id: "rejected", label: "Rejected" },
];

function Row({ p, onDone }: { p: Card; onDone: () => void }) {
  const [confirm, setConfirm] = useState<"" | "ok" | "no">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const act = async (action: "confirm" | "reject") => {
    setBusy(true);
    setError("");
    try {
      await api(`/api/admin/payments/${p.id}/${action}`, { method: "POST", body: action === "reject" ? { reason: "Payment not received" } : undefined });
      onDone();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };
  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-display text-2xl font-extrabold">{inr(p.amount_inr)}</div>
          <div className="text-sm">UTR <span className="font-mono font-semibold">{p.utr}</span> · Ref <span className="font-mono">{p.order_id}</span></div>
          <div className="text-xs text-ink-500">{p.traveller.name} ({p.traveller.email}) · {new Date(p.created_at).toLocaleString("en-IN")}</div>
        </div>
        {p.status === "submitted" && (
          <div className="flex flex-wrap items-center gap-2">
            {confirm === "" && (
              <>
                <button className="btn-outline px-3 py-1.5" onClick={() => setConfirm("no")}><XCircle size={15} /> Not received</button>
                <button className="btn-dark px-3 py-1.5" onClick={() => setConfirm("ok")}><CheckCircle2 size={15} /> Money received</button>
              </>
            )}
            {confirm === "ok" && (
              <>
                <span className="text-xs text-ink-600">Confirm {inr(p.amount_inr)} with UTR {p.utr} is in your account?</span>
                <button className="btn-ghost px-3 py-1.5" onClick={() => setConfirm("")}>Back</button>
                <button className="btn-primary px-3 py-1.5" disabled={busy} onClick={() => act("confirm")}>{busy && <Loader2 size={14} className="animate-spin" />} Yes, book it</button>
              </>
            )}
            {confirm === "no" && (
              <>
                <span className="text-xs text-ink-600">Reject — nothing will be booked.</span>
                <button className="btn-ghost px-3 py-1.5" onClick={() => setConfirm("")}>Back</button>
                <button className="btn-dark px-3 py-1.5" disabled={busy} onClick={() => act("reject")}>Reject payment</button>
              </>
            )}
          </div>
        )}
      </div>
      <div className="mt-3 rounded-lg bg-cream p-3 text-sm">
        <div className="font-semibold">{p.trip}</div>
        <ul className="mt-1 list-disc pl-5 text-xs text-ink-600">{p.items.map((i: string) => <li key={i}>{i}</li>)}</ul>
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}

export default function Admin() {
  const [tab, setTab] = useState("submitted");
  const [rows, setRows] = useState<Card[] | null>(null);
  const load = useCallback(() => {
    setRows(null);
    api<Card[]>(`/api/admin/payments?status=${tab}`).then(setRows).catch(() => setRows([]));
  }, [tab]);
  useEffect(load, [load]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <PageHeader title="Payment verification" text="Open your UPI / bank app, find a credit with the same UTR and amount, then confirm. Trips are booked only after you confirm." />
      <div className="mb-4 flex gap-2">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} className={cx("rounded-full px-4 py-2 text-sm font-semibold", tab === t.id ? "bg-ink-950 text-mustard-400" : "bg-ink-100")}>{t.label}</button>
        ))}
      </div>
      {rows === null ? <Loader2 className="animate-spin text-mustard-600" /> : rows.length === 0 ? (
        <p className="text-sm text-ink-500">Nothing here.</p>
      ) : (
        <div className="space-y-3">{rows.map((p) => <Row key={p.id} p={p} onDone={load} />)}</div>
      )}
    </div>
  );
}
