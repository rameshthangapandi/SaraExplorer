import { ArrowRight, CalendarDays, Check, Hotel, Loader2, Plane, Search, Sparkles, TrainFront, Users, X } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { MonthStrip, Suggestions } from "../components/cards/Cards";
import ConsentCard from "../components/cards/ConsentCard";
import { api, type Card } from "../lib/api";
import { addDays, cx, day, duration, inr, isoDay, time } from "../lib/format";

type Meta = { origins: string[]; destinations: { slug: string; name: string; state: string }[] };
type Section = { loading: boolean; error?: string; options: Card[] };
type Kind = "out" | "back" | "stay";

const empty: Section = { loading: false, options: [] };
const today = isoDay(new Date());

function Field({ label, icon, children }: { label: string; icon: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <span className="label flex items-center gap-1.5">{icon} {label}</span>
      {children}
    </label>
  );
}

function SelectRow({ selected, onSelect, children, disabled }: { selected: boolean; onSelect: () => void; children: ReactNode; disabled?: boolean }) {
  return (
    <button type="button" onClick={onSelect} disabled={disabled}
      className={cx("flex w-full flex-wrap items-center gap-x-4 gap-y-1.5 rounded-xl border-2 px-3 py-2.5 text-left transition",
        selected ? "border-ink-950 bg-mustard-50" : "border-ink-100 bg-white hover:border-ink-300")}>
      <span className={cx("grid size-5 shrink-0 place-items-center rounded-full border-2", selected ? "border-ink-950 bg-ink-950 text-mustard-400" : "border-ink-300")}>
        {selected && <Check size={12} strokeWidth={3} />}
      </span>
      {children}
    </button>
  );
}

function TransportOption({ o }: { o: Card }) {
  const isTrain = "train_no" in o;
  return (
    <>
      <div className="min-w-[150px] flex-1">
        <div className="text-sm font-semibold">{isTrain ? o.train_name : o.airline}</div>
        <div className="text-[11px] text-ink-500">{isTrain ? `#${o.train_no} · ${o.class}` : `${o.flight_no} · ${o.stops ? `1 stop via ${o.via}` : "non-stop"}`}</div>
      </div>
      <div className="text-sm"><b>{time(o.depart)}</b> → <b>{time(o.arrive)}</b> <span className="text-[11px] text-ink-500">· {duration(o.duration_min)}</span></div>
      {isTrain && (
        <span className={cx("rounded-full px-2 py-0.5 text-[11px] font-semibold",
          o.availability.startsWith("AVAILABLE") ? "bg-emerald-50 text-emerald-700" : o.availability.startsWith("RAC") ? "bg-mustard-100 text-mustard-800" : "bg-red-50 text-red-700")}>
          {o.availability}{o.availability.startsWith("WL") && ` · ${Math.round(o.confirm_chance * 100)}% likely`}
        </span>
      )}
      <div className="ml-auto text-right font-display font-bold">{inr(o.price_total)}</div>
    </>
  );
}

function HotelOption({ o }: { o: Card }) {
  return (
    <>
      <div className="min-w-[180px] flex-1">
        <div className="text-sm font-semibold">{o.hotel}</div>
        <div className="text-[11px] text-ink-500"><span className="text-mustard-600">{"★".repeat(o.stars)}</span> · {o.rating}/5 ({o.reviews} reviews) · {o.amenities.slice(0, 2).join(" · ")}</div>
        {o.free_cancellation_until && <div className="text-[11px] font-medium text-emerald-700">Free cancellation till {day(o.free_cancellation_until)}</div>}
      </div>
      <div className="ml-auto text-right">
        <div className="font-display font-bold">{inr(o.price_total)}</div>
        <div className="text-[11px] text-ink-500">{inr(o.price_per_night)}/night × {o.rooms} room{o.rooms > 1 ? "s" : ""}</div>
      </div>
    </>
  );
}

const SORTS: Record<string, (a: Card, b: Card) => number> = {
  cheapest: (a, b) => a.price_total - b.price_total,
  earliest: (a, b) => (a.depart ?? "").localeCompare(b.depart ?? ""),
  fastest: (a, b) => (a.duration_min ?? 0) - (b.duration_min ?? 0),
};

function ResultBlock({ title, icon, section, selectedId, onSelect, render, empty: emptyText, transport = false }: {
  title: string; icon: ReactNode; section: Section; selectedId?: string; onSelect: (o: Card) => void; render: (o: Card) => ReactNode; empty: string; transport?: boolean;
}) {
  const [all, setAll] = useState(false);
  const [kind, setKind] = useState("all");
  const [sort, setSort] = useState("cheapest");
  const hasBoth = transport && section.options.some((o) => "train_no" in o) && section.options.some((o) => "flight_no" in o);
  const filtered = section.options
    .filter((o) => kind === "all" || (kind === "train" ? "train_no" in o : "flight_no" in o))
    .sort(SORTS[sort]);
  const shown = all ? filtered : filtered.slice(0, 4);
  return (
    <div className="card p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 font-bold">{icon} {title}</h3>
        {transport && section.options.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            {hasBoth && [["all", "All"], ["flight", "Flights"], ["train", "Trains"]].map(([id, label]) => (
              <button key={id} type="button" onClick={() => setKind(id)}
                className={cx("rounded-full px-3 py-1 text-xs font-semibold", kind === id ? "bg-ink-950 text-mustard-400" : "bg-ink-100 hover:bg-ink-200")}>{label}</button>
            ))}
            <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort by" className="rounded-full border border-ink-200 bg-white px-2.5 py-1 text-xs font-semibold">
              <option value="cheapest">Cheapest</option>
              <option value="earliest">Earliest</option>
              <option value="fastest">Fastest</option>
            </select>
          </div>
        )}
      </div>
      {section.loading ? (
        <div className="flex items-center gap-2 text-sm text-ink-500"><Loader2 size={16} className="animate-spin" /> Searching…</div>
      ) : section.error ? (
        <p className="text-sm text-ink-500">{section.error}</p>
      ) : section.options.length === 0 ? (
        <p className="text-sm text-ink-500">{emptyText}</p>
      ) : (
        <div className="space-y-2">
          {shown.length === 0 && <p className="text-sm text-ink-500">No {kind}s on this route.</p>}
          {shown.map((o) => <SelectRow key={o.id} selected={o.id === selectedId} onSelect={() => onSelect(o)}>{render(o)}</SelectRow>)}
          {filtered.length > 4 && (
            <button type="button" className="text-xs font-semibold text-mustard-700 hover:underline" onClick={() => setAll(!all)}>
              {all ? "Show fewer" : `Show all ${filtered.length} options`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function Plan() {
  const [params] = useSearchParams();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [form, setForm] = useState({
    origin: "Delhi", destination: params.get("to") ?? "goa", depart: addDays(today, 21), nights: 3, adults: 2,
    mode: "both", budget: "", roundTrip: true, total: "", objective: "balanced",
  });
  const [searched, setSearched] = useState<typeof form | null>(null);
  const [out, setOut] = useState<Section>(empty);
  const [back, setBack] = useState<Section>(empty);
  const [stay, setStay] = useState<Section>(empty);
  const [advice, setAdvice] = useState<Card[] | null>(null);
  const [bestTime, setBestTime] = useState<Card | null>(null);
  const [picked, setPicked] = useState<Record<Kind, Card | undefined>>({ out: undefined, back: undefined, stay: undefined });
  const [consent, setConsent] = useState<Card | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [planning, setPlanning] = useState(false);
  const [autoNote, setAutoNote] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    api<Meta>("/api/meta/places").then(setMeta).catch(() => undefined);
  }, []);

  const destName = meta?.destinations.find((d) => d.slug === form.destination)?.name ?? form.destination;

  async function transport(origin: string, dest: string, date: string, adults: number, mode: string): Promise<Section> {
    const calls: Promise<Card[]>[] = [];
    const run = (path: string) => api<Card>(path, { method: "POST", body: { origin, destination: dest, date, adults } })
      .then((c) => c.options as Card[]).catch(() => [] as Card[]);
    if (mode !== "train") calls.push(run("/api/search/flights"));
    if (mode !== "flight") calls.push(run("/api/search/trains"));
    const options = (await Promise.all(calls)).flat().sort((a, b) => a.price_total - b.price_total);
    return { loading: false, options, error: options.length ? undefined : `No ${mode === "both" ? "flights or trains" : mode + "s"} found for this route. Try another departure city.` };
  }

  const search = async (e?: FormEvent) => {
    e?.preventDefault();
    setError("");
    setAutoNote(null);
    setConsent(null);
    setPicked({ out: undefined, back: undefined, stay: undefined });
    setAdvice(null);
    const f = { ...form };
    setSearched(f);
    const ret = addDays(f.depart, f.nights);
    setOut({ ...empty, loading: true });
    setBack(f.roundTrip ? { ...empty, loading: true } : empty);
    setStay({ ...empty, loading: true });
    transport(f.origin, destName, f.depart, f.adults, f.mode).then(setOut);
    if (f.roundTrip) transport(destName, f.origin, ret, f.adults, f.mode).then(setBack);
    api<Card>("/api/search/hotels", {
      method: "POST",
      body: { city: destName, check_in: f.depart, check_out: ret, guests: f.adults, max_price_per_night: f.budget ? +f.budget : null },
    }).then((c) => setStay({ loading: false, options: c.options })).catch((err) => setStay({ loading: false, options: [], error: err.message }));
    api<{ suggestions: Card[] }>("/api/strategist/advice", {
      method: "POST", body: { destination: f.destination, origin: f.origin, travel_date: f.depart, nights: f.nights, adults: f.adults },
    }).then((r) => setAdvice(r.suggestions)).catch(() => setAdvice([]));
    api<Card>(`/api/strategist/best-time/${f.destination}`).then(setBestTime).catch(() => undefined);
  };

  /** Constraint solver: picks the best onward + stay + return that satisfies every constraint. */
  const autoPlan = async () => {
    search();
    setPlanning(true);
    try {
      const res = await api<Card>("/api/plan/auto", {
        method: "POST",
        body: {
          origin: form.origin, destination: form.destination, depart: form.depart, nights: form.nights, adults: form.adults,
          mode: form.mode === "both" ? "any" : form.mode, round_trip: form.roundTrip, objective: form.objective,
          budget_total: form.total ? +form.total : null, hotel_max_per_night: form.budget ? +form.budget : null,
        },
      });
      if (res.status === "ok") {
        setPicked({ out: res.plan.out, back: res.plan.back ?? undefined, stay: res.plan.stay });
        setAutoNote({ ok: true, text: `Sara checked ${res.candidates_checked} combinations and picked the best one that meets all your conditions.` });
      } else {
        setAutoNote({ ok: false, text: res.reasons.join(" ") });
      }
    } catch (err) {
      setAutoNote({ ok: false, text: (err as Error).message });
    } finally {
      setPlanning(false);
    }
  };

  const chosen = useMemo(() => (Object.values(picked).filter(Boolean) as Card[]), [picked]);
  const total = chosen.reduce((s, o) => s + o.price_total, 0);
  const toggle = (kind: Kind) => (o: Card) => {
    setConsent(null);
    setPicked((p) => ({ ...p, [kind]: p[kind]?.id === o.id ? undefined : o }));
  };

  const review = async () => {
    setCreating(true);
    setError("");
    try {
      setConsent(await api<Card>("/api/consents", {
        method: "POST",
        body: { option_ids: chosen.map((o) => o.id), title: `${searched?.origin} → ${destName}, ${day(searched!.depart)} · ${searched?.nights} nights` },
      }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setCreating(false);
    }
  };

  const minReturn = addDays(form.depart, 1);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold sm:text-4xl">Plan & Book</h1>
          <p className="mt-1 text-ink-500">Pick your trip, compare options, and book after you approve and pay.</p>
        </div>
        <Link to="/app/explore" className="btn-outline">Not sure where? Explore <ArrowRight size={16} /></Link>
      </div>

      <form onSubmit={search} className="card grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="From" icon={<Plane size={13} />}>
          <select className="input" value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value })}>
            {meta?.origins.map((c) => <option key={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="To" icon={<Sparkles size={13} />}>
          <select className="input" value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })}>
            {meta?.destinations.map((d) => <option key={d.slug} value={d.slug}>{d.name}, {d.state}</option>)}
          </select>
        </Field>
        <Field label="Depart" icon={<CalendarDays size={13} />}>
          <input type="date" className="input" min={today} value={form.depart} required onChange={(e) => setForm({ ...form, depart: e.target.value })} />
        </Field>
        <Field label="Nights" icon={<Hotel size={13} />}>
          <select className="input" value={form.nights} onChange={(e) => setForm({ ...form, nights: +e.target.value })}>
            {Array.from({ length: 14 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n} night{n > 1 ? "s" : ""} · back {day(addDays(form.depart || minReturn, n))}</option>)}
          </select>
        </Field>
        <Field label="Travellers" icon={<Users size={13} />}>
          <select className="input" value={form.adults} onChange={(e) => setForm({ ...form, adults: +e.target.value })}>
            {Array.from({ length: 9 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n} adult{n > 1 ? "s" : ""}</option>)}
          </select>
        </Field>
        <Field label="Travel by" icon={<TrainFront size={13} />}>
          <select className="input" value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}>
            <option value="both">Flight or train</option>
            <option value="flight">Flight only</option>
            <option value="train">Train only</option>
          </select>
        </Field>
        <Field label="Hotel budget / night" icon={<Hotel size={13} />}>
          <select className="input" value={form.budget} onChange={(e) => setForm({ ...form, budget: e.target.value })}>
            <option value="">Any budget</option>
            <option value="3000">Up to ₹3,000</option>
            <option value="6000">Up to ₹6,000</option>
            <option value="10000">Up to ₹10,000</option>
          </select>
        </Field>
        <Field label="Total trip budget" icon={<Sparkles size={13} />}>
          <select className="input" value={form.total} onChange={(e) => setForm({ ...form, total: e.target.value })}>
            <option value="">No limit</option>
            {[15000, 25000, 40000, 60000, 100000, 150000, 250000].map((v) => <option key={v} value={v}>Up to ₹{v.toLocaleString("en-IN")}</option>)}
          </select>
        </Field>
        <Field label="Priority" icon={<Check size={13} />}>
          <select className="input" value={form.objective} onChange={(e) => setForm({ ...form, objective: e.target.value })}>
            <option value="balanced">Best balance</option>
            <option value="cheapest">Lowest price</option>
            <option value="comfort">Most comfortable</option>
          </select>
        </Field>
        <div className="flex flex-col justify-end gap-2 sm:col-span-2">
          <label className="flex items-center gap-2 text-sm text-ink-600">
            <input type="checkbox" className="size-4 accent-ink-950" checked={form.roundTrip} onChange={(e) => setForm({ ...form, roundTrip: e.target.checked })} />
            Include return journey
          </label>
          <div className="grid grid-cols-2 gap-2">
            <button className="btn-outline w-full py-3"><Search size={16} /> Search &amp; compare</button>
            <button type="button" onClick={autoPlan} disabled={planning} className="btn-primary w-full py-3">
              {planning ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />} Auto-plan best trip
            </button>
          </div>
        </div>
      </form>

      {!searched ? (
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {[["1", "Choose", "Pick where, when and how — no typing needed."], ["2", "Compare", "Flights, trains and stays side by side, with Sara's strategy."], ["3", "Approve & pay", "Pay by UPI. Booked once your payment is confirmed."]].map(([n, t, d]) => (
            <div key={n} className="border-t-4 border-ink-950 pt-3">
              <span className="font-display text-sm font-extrabold text-mustard-600">0{n}</span>
              <div className="font-bold">{t}</div>
              <p className="text-sm text-ink-500">{d}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-6 grid items-start gap-6 lg:grid-cols-[1fr_340px]">
          <div className="space-y-4">
            <ResultBlock title={`${searched.origin} → ${destName} · ${day(searched.depart)}`} icon={<Plane size={16} className="text-mustard-600" />}
              section={out} selectedId={picked.out?.id} onSelect={toggle("out")} render={(o) => <TransportOption o={o} />} empty="No options." transport />
            {searched.roundTrip && (
              <ResultBlock title={`${destName} → ${searched.origin} · ${day(addDays(searched.depart, searched.nights))}`} icon={<Plane size={16} className="rotate-180 text-mustard-600" />}
                section={back} selectedId={picked.back?.id} onSelect={toggle("back")} render={(o) => <TransportOption o={o} />} empty="No options." transport />
            )}
            <ResultBlock title={`Stays in ${destName} · ${searched.nights} night${searched.nights > 1 ? "s" : ""}`} icon={<Hotel size={16} className="text-mustard-600" />}
              section={stay} selectedId={picked.stay?.id} onSelect={toggle("stay")} render={(o) => <HotelOption o={o} />} empty="No stays in this budget — try a higher one." />
          </div>

          <aside className="space-y-4 lg:sticky lg:top-4">
            <div className="card overflow-hidden">
              <div className="bg-ink-950 px-4 py-3 text-cream">
                <div className="font-bold">Your trip</div>
                <div className="text-xs text-ink-300">{destName} · {day(searched.depart)} – {day(addDays(searched.depart, searched.nights))} · {searched.adults} adult{searched.adults > 1 ? "s" : ""}</div>
              </div>
              <div className="space-y-2 p-4">
                {autoNote && (
                  <p className={cx("rounded-lg p-2.5 text-xs", autoNote.ok ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-700")}>{autoNote.text}</p>
                )}
                {chosen.length === 0 && <p className="text-sm text-ink-500">Select a journey and a stay, or press “Auto-plan best trip”.</p>}
                {(["out", "back", "stay"] as Kind[]).map((k) => picked[k] && (
                  <div key={k} className="flex items-start gap-2 text-sm">
                    <div className="flex-1">
                      <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">{k === "out" ? "Onward" : k === "back" ? "Return" : "Stay"}</div>
                      <div className="font-medium">{picked[k]!.airline ?? picked[k]!.train_name ?? picked[k]!.hotel}</div>
                    </div>
                    <span className="font-semibold">{inr(picked[k]!.price_total)}</span>
                    <button onClick={() => setPicked((p) => ({ ...p, [k]: undefined }))} className="text-ink-300 hover:text-ink-900" aria-label="Remove"><X size={14} /></button>
                  </div>
                ))}
                {chosen.length > 0 && (
                  <>
                    <div className="perforation my-3" />
                    <div className="flex items-baseline justify-between">
                      <span className="text-sm font-semibold text-ink-500">Total</span>
                      <span className="font-display text-2xl font-extrabold">{inr(total)}</span>
                    </div>
                    {error && <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
                    {!consent && (
                      <button onClick={review} disabled={creating} className="btn-dark mt-2 w-full py-3">
                        {creating && <Loader2 size={16} className="animate-spin" />} Review & approve
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
            {consent && <ConsentCard card={consent} />}
            <div className="card p-4">
              <h3 className="mb-3 flex items-center gap-2 font-bold"><Sparkles size={16} className="text-mustard-600" /> Sara's strategy</h3>
              {advice === null ? <Loader2 size={16} className="animate-spin text-mustard-600" /> : <Suggestions items={advice} />}
            </div>
            {bestTime && (
              <div className="card p-4">
                <h3 className="mb-3 font-bold">Best months for {bestTime.destination}</h3>
                <MonthStrip months={bestTime.months} />
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
