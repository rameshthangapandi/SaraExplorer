import { CheckCircle2, Loader2, Pencil, XCircle } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type Card } from "../lib/api";
import { useAuth } from "../lib/auth";
import { cx, inr } from "../lib/format";
import { PageHeader } from "./Strategist";

const PAY_TABS = [
  { id: "submitted", label: "To confirm" },
  { id: "paid", label: "Received" },
  { id: "rejected", label: "Not received" },
];

function PaymentRow({ p, onDone }: { p: Card; onDone: () => void }) {
  const [confirm, setConfirm] = useState<"" | "ok" | "no">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const act = async (action: "confirm" | "reject") => {
    setBusy(true);
    setError("");
    try {
      await api(`/api/vendor-portal/payments/${p.id}/${action}`, { method: "POST", body: action === "reject" ? { reason: "Payment not received" } : undefined });
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
          <div className="flex items-center gap-2">
            <span className="font-display text-2xl font-extrabold">{inr(p.amount_inr)}</span>
            <span className="text-sm text-ink-500">to <b className="text-ink-900">{p.vendor.name}</b></span>
            {p.vendor.pending && <span className="rounded bg-ink-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-ink-600">not live</span>}
          </div>
          <div className="text-sm">UTR <span className="font-mono font-semibold">{p.utr}</span> · Ref <span className="font-mono">{p.order_id}</span></div>
          <div className="text-xs text-ink-500">From {p.traveller.name} ({p.traveller.email}) · {new Date(p.created_at).toLocaleString("en-IN")}</div>
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
                <span className="text-xs text-ink-600">{inr(p.amount_inr)} with UTR {p.utr} is in "the vendor's" account?</span>
                <button className="btn-ghost px-3 py-1.5" onClick={() => setConfirm("")}>Back</button>
                <button className="btn-primary px-3 py-1.5" disabled={busy} onClick={() => act("confirm")}>{busy && <Loader2 size={14} className="animate-spin" />} Yes, book it</button>
              </>
            )}
            {confirm === "no" && (
              <>
                <span className="text-xs text-ink-600">Nothing will be booked.</span>
                <button className="btn-ghost px-3 py-1.5" onClick={() => setConfirm("")}>Back</button>
                <button className="btn-dark px-3 py-1.5" disabled={busy} onClick={() => act("reject")}>Mark not received</button>
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

function Payments() {
  const [tab, setTab] = useState("submitted");
  const [rows, setRows] = useState<Card[] | null>(null);
  const load = useCallback(() => {
    setRows(null);
    api<Card[]>(`/api/vendor-portal/payments?status=${tab}`).then(setRows).catch(() => setRows([]));
  }, [tab]);
  useEffect(load, [load]);
  return (
    <>
      <div className="mb-4 flex flex-wrap gap-2">
        {PAY_TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} className={cx("rounded-full px-4 py-2 text-sm font-semibold", tab === t.id ? "bg-ink-950 text-mustard-400" : "bg-ink-100")}>{t.label}</button>
        ))}
      </div>
      {rows === null ? <Loader2 className="animate-spin text-mustard-600" /> : rows.length === 0 ? (
        <p className="text-sm text-ink-500">Nothing here.</p>
      ) : (
        <div className="space-y-3">{rows.map((p) => <PaymentRow key={p.id} p={p} onDone={load} />)}</div>
      )}
    </>
  );
}

function VendorRow({ v, onSaved }: { v: Card; onSaved: (v: Card) => void }) {
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState({ upi_id: v.pending ? "" : v.upi_id, owner_email: v.owner_email ?? "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onSaved(await api<Card>(`/api/admin/vendors/${v.id}`, {
        method: "PATCH",
        body: { upi_id: form.upi_id.trim(), owner_email: form.owner_email.trim() || undefined, live: true },
      }));
      setEdit(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-[180px] flex-1">
          <div className="font-semibold">{v.name} <span className="chip ml-1 capitalize">{v.kind}</span></div>
          <div className="font-mono text-xs text-ink-500">{v.upi_id}{v.owner_email && <span className="font-sans"> · login: {v.owner_email}</span>}</div>
        </div>
        <span className={cx("rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase", v.pending ? "bg-ink-100 text-ink-600" : "bg-emerald-50 text-emerald-700")}>{v.pending ? "Not live" : "Live"}</span>
        <button className="btn-outline px-3 py-1.5" onClick={() => setEdit(!edit)}><Pencil size={14} /> {v.pending ? "Add real details" : "Edit"}</button>
      </div>
      {edit && (
        <form onSubmit={save} className="mt-4 grid gap-3 border-t border-ink-100 pt-4 sm:grid-cols-[1fr_1fr_auto]">
          <label><span className="label">Vendor's UPI ID</span>
            <input className="input" required placeholder="homestay@okaxis" value={form.upi_id} onChange={(e) => setForm({ ...form, upi_id: e.target.value })} />
          </label>
          <label><span className="label">Vendor login email</span>
            <input className="input" type="email" placeholder="owner@example.com" value={form.owner_email} onChange={(e) => setForm({ ...form, owner_email: e.target.value })} />
          </label>
          <button className="btn-primary self-end" disabled={busy}>{busy && <Loader2 size={14} className="animate-spin" />} Save & go live</button>
          {error && <p className="text-sm text-red-600 sm:col-span-3">{error}</p>}
          <p className="text-xs text-ink-500 sm:col-span-3">Once live, travellers pay this UPI ID directly and the vendor (signed in with this email) confirms payments in their Vendor portal.</p>
        </form>
      )}
    </div>
  );
}

function Vendors() {
  const [rows, setRows] = useState<Card[] | null>(null);
  useEffect(() => {
    api<Card[]>("/api/admin/vendors").then(setRows).catch(() => setRows([]));
  }, []);
  if (rows === null) return <Loader2 className="animate-spin text-mustard-600" />;
  if (rows.length === 0) return <p className="text-sm text-ink-500">Vendors appear here automatically when travellers approve trips.</p>;
  return <div className="space-y-3">{rows.map((v) => <VendorRow key={v.id} v={v} onSaved={(nv) => setRows((all) => all!.map((x) => (x.id === nv.id ? nv : x)))} />)}</div>;
}

export default function Admin() {
  const { user } = useAuth();
  const [section, setSection] = useState<"payments" | "vendors">("payments");
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <PageHeader title="Vendor portal" text="Travellers pay vendors directly. Check the vendor's UPI / bank app for the same UTR and amount, then confirm — only then is that part of the trip booked." />
      {user?.is_admin && (
        <>
          <div className="mb-5 flex gap-1 rounded-full bg-ink-100 p-1 sm:w-fit">
            {(["payments", "vendors"] as const).map((s) => (
              <button key={s} onClick={() => setSection(s)} className={cx("flex-1 rounded-full px-5 py-2 text-sm font-semibold capitalize", section === s ? "bg-white shadow" : "text-ink-500")}>{s}</button>
            ))}
          </div>
          {section === "payments" && (
            <p className="mb-4 rounded-xl bg-mustard-50 p-3 text-xs text-mustard-800">As admin you confirm payments for vendors that are <b>not live yet</b>. Live vendors confirm their own payments.</p>
          )}
        </>
      )}
      {section === "payments" ? <Payments /> : <Vendors />}
    </div>
  );
}
