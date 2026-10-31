import { Bike, Bus, Car, Clock, ExternalLink, Loader2, LocateFixed, MapPin, Sparkles, TrainFront, Users } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type Card } from "../lib/api";
import { cx, inr } from "../lib/format";
import { GROUPS } from "../lib/groups";
import { PageHeader } from "./Strategist";

const MODE_ICON: Record<string, ReactNode> = {
  bus: <Bus size={18} />, metro: <TrainFront size={18} />, bike: <Bike size={18} />, auto: <Car size={18} />,
  cab: <Car size={18} />, sedan: <Car size={18} />, suv: <Car size={18} />,
};
const PROVIDER_STYLE: Record<string, string> = {
  Uber: "bg-ink-950 text-white", Ola: "bg-[#c6e04f] text-ink-950", Rapido: "bg-[#f9d71c] text-ink-950",
  Metro: "bg-[#2b6cb0] text-white", "City bus": "bg-[#2f855a] text-white",
};

export function RideResults({ data }: { data: Card }) {
  const maxPP = Math.max(...data.options.map((o: Card) => o.per_person));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm text-ink-600">
        <MapPin size={15} className="text-mustard-600" /> <b>{data.from.name}</b> → <b>{data.to.name}</b>
        <span className="chip">{data.distance_km} km by road</span>
        {data.peak && <span className="chip border-mustard-300 text-mustard-800">Peak hour: cabs may surge</span>}
        {data.night && <span className="chip border-ink-300">Night fares apply</span>}
      </div>
      {data.recommended && (
        <div className="flex items-start gap-3 rounded-2xl border-2 border-ink-950 bg-mustard-50 p-4">
          <Sparkles size={20} className="mt-0.5 shrink-0 text-mustard-700" />
          <div><div className="text-[11px] font-bold uppercase tracking-wider text-mustard-800">Sara recommends</div><p className="text-sm text-ink-800">{data.reason}</p></div>
        </div>
      )}
      <div className="space-y-2">
        {data.options.map((o: Card, i: number) => (
          <div key={i} className={cx("flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border px-3 py-2.5", o.badges.includes("Recommended") ? "border-ink-950 bg-white" : "border-ink-100 bg-white")}>
            <span className={cx("grid size-9 place-items-center rounded-lg", PROVIDER_STYLE[o.provider] ?? "bg-ink-100")}>{MODE_ICON[o.mode]}</span>
            <div className="min-w-[150px] flex-1">
              <div className="text-sm font-semibold">{o.provider} · {o.product}</div>
              <div className="text-[11px] text-ink-500">{o.mode_label}{o.vehicles > 1 ? ` · ${o.vehicles} vehicles` : ""}{o.surge ? " · surge" : ""}{o.night_fare ? " · night fare" : ""}</div>
            </div>
            <div className="hidden w-40 sm:block">
              <div className="h-2 overflow-hidden rounded-full bg-ink-100"><div className="h-full rounded-full bg-mustard-500" style={{ width: `${(o.per_person / maxPP) * 100}%` }} /></div>
            </div>
            <div className="flex items-center gap-1 text-xs text-ink-600"><Clock size={13} /> {o.total_min} min</div>
            <div className="w-28 text-right">
              <div className="font-display font-bold">{inr(o.fare_min)}–{o.fare_max.toLocaleString("en-IN")}</div>
              <div className="text-[11px] text-ink-500">{inr(o.per_person)} per person</div>
            </div>
            <div className="flex w-full items-center gap-1.5 sm:w-auto">
              {o.badges.map((b: string) => (
                <span key={b} className={cx("rounded-full px-2 py-0.5 text-[10px] font-bold uppercase", b === "Recommended" ? "bg-ink-950 text-mustard-400" : b === "Cheapest" ? "bg-emerald-50 text-emerald-700" : "bg-sky-50 text-sky-700")}>{b}</span>
              ))}
              <a href={o.booking_url} target="_blank" rel="noopener noreferrer" className="ml-auto inline-flex items-center gap-1 rounded-full border border-ink-200 px-3 py-1 text-xs font-semibold hover:border-ink-900">
                {o.mode === "bus" || o.mode === "metro" ? "Route" : `Open ${o.provider}`} <ExternalLink size={11} />
              </a>
            </div>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-ink-400">Fares are estimates from each service's typical base, distance and time charges with peak and night pricing; the final fare is shown in the operator's app.</p>
    </div>
  );
}

export default function Rides() {
  const [params] = useSearchParams();
  const now = new Date().getHours();
  const [form, setForm] = useState({ from: params.get("from") ?? "", to: params.get("to") ?? "", hour: now, people: 2, bags: 1, priority: "value", group: "" });
  const [here, setHere] = useState<{ lat: number; lon: number } | null>(null);
  const [data, setData] = useState<Card | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const locate = () => navigator.geolocation.getCurrentPosition(
    (p) => { setHere({ lat: p.coords.latitude, lon: p.coords.longitude }); setForm((f) => ({ ...f, from: "My location" })); },
    () => setError("Location access was blocked."),
  );

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setData(await api<Card>("/api/local/compare", {
        method: "POST",
        body: {
          from_place: here && form.from === "My location" ? null : form.from, to_place: form.to,
          from_lat: here && form.from === "My location" ? here.lat : null, from_lon: here && form.from === "My location" ? here.lon : null,
          hour: form.hour, people: form.people, bags: form.bags, priority: form.priority, traveller_type: form.group || null,
        },
      }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <PageHeader title="Local Rides" text="Compare city bus, metro, Rapido, Ola and Uber for any ride, by price per person and time, and get a recommendation for your group." />
      <form onSubmit={submit} className="card grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4">
        <label className="sm:col-span-2"><span className="label">From</span>
          <div className="flex gap-2">
            <input className="input" required placeholder="e.g. Jaipur airport" value={form.from} onChange={(e) => setForm({ ...form, from: e.target.value })} maxLength={120} />
            <button type="button" onClick={locate} className="btn-outline px-3" title="Use my location" aria-label="Use my location"><LocateFixed size={16} /></button>
          </div>
        </label>
        <label className="sm:col-span-2"><span className="label">To</span>
          <input className="input" required placeholder="e.g. Hawa Mahal, Jaipur" value={form.to} onChange={(e) => setForm({ ...form, to: e.target.value })} maxLength={120} />
        </label>
        <label><span className="label">Time</span>
          <select className="input" value={form.hour} onChange={(e) => setForm({ ...form, hour: +e.target.value })}>
            {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{h === now ? "Now · " : ""}{String(h).padStart(2, "0")}:00</option>)}
          </select>
        </label>
        <label><span className="label flex items-center gap-1"><Users size={12} /> People</span>
          <select className="input" value={form.people} onChange={(e) => setForm({ ...form, people: +e.target.value })}>
            {Array.from({ length: 8 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label><span className="label">Bags</span>
          <select className="input" value={form.bags} onChange={(e) => setForm({ ...form, bags: +e.target.value })}>
            {Array.from({ length: 7 }, (_, i) => i).map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label><span className="label">Who's travelling</span>
          <select className="input" value={form.group} onChange={(e) => setForm({ ...form, group: e.target.value })}>
            {GROUPS.map((g) => <option key={g.id} value={g.id}>{g.label}</option>)}
          </select>
        </label>
        <label className="sm:col-span-2 lg:col-span-3"><span className="label">Priority</span>
          <div className="flex flex-wrap gap-1.5">
            {[["value", "Best value"], ["cheapest", "Cheapest"], ["fastest", "Fastest"], ["comfort", "Most comfortable"]].map(([id, l]) => (
              <button key={id} type="button" onClick={() => setForm({ ...form, priority: id })}
                className={cx("rounded-full px-4 py-2 text-sm font-semibold", form.priority === id ? "bg-ink-950 text-mustard-400" : "bg-ink-100 hover:bg-ink-200")}>{l}</button>
            ))}
          </div>
        </label>
        <div className="flex items-end"><button className="btn-primary w-full py-3" disabled={busy}>{busy && <Loader2 size={16} className="animate-spin" />} Compare rides</button></div>
      </form>
      {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {data && <div className="card mt-6 p-5"><RideResults data={data} /></div>}
    </div>
  );
}
