import { Compass, Loader2, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { MonthStrip, Suggestions } from "../components/cards/Cards";
import { api, type Card } from "../lib/api";
import { cx, day, isoDay } from "../lib/format";

type Dest = { slug: string; name: string; state: string; tags: string[] };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const INTERESTS = ["", "beach", "mountains", "heritage", "spiritual", "adventure", "honeymoon", "food", "offbeat"];

function PageHeader({ title, text }: { title: string; text: string }) {
  return (
    <div className="mb-8">
      <h1 className="text-3xl font-extrabold sm:text-4xl">{title}</h1>
      <p className="mt-1.5 max-w-2xl text-ink-500">{text}</p>
    </div>
  );
}

export { PageHeader };

export default function Strategist() {
  const [dests, setDests] = useState<Dest[]>([]);
  const [slug, setSlug] = useState("goa");
  const [best, setBest] = useState<Card | null>(null);
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [interest, setInterest] = useState("");
  const [where, setWhere] = useState<Card | null>(null);
  const [form, setForm] = useState({ destination: "goa", origin: "Delhi", travel_date: "", nights: 3, adults: 2 });
  const [advice, setAdvice] = useState<Card[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Dest[]>("/api/strategist/destinations").then(setDests).catch(() => undefined);
  }, []);
  useEffect(() => {
    api<Card>(`/api/strategist/best-time/${slug}`).then(setBest).catch(() => undefined);
  }, [slug]);
  useEffect(() => {
    api<Card>(`/api/strategist/where?month=${month}${interest ? `&interest=${interest}` : ""}`).then(setWhere).catch(() => undefined);
  }, [month, interest]);

  const runAdvice = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api<{ suggestions: Card[] }>("/api/strategist/advice", {
        method: "POST",
        body: { ...form, origin: form.origin || null, travel_date: form.travel_date || null },
      });
      setAdvice(res.suggestions);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const minDate = isoDay(new Date());

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <PageHeader title="The Strategist" text="Smart timing for every trip: when to go, when to book, where to fly into, and what to watch out for." />

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Trip advice */}
        <form onSubmit={runAdvice} className="card space-y-4 p-5 lg:col-span-2">
          <h2 className="flex items-center gap-2 text-lg font-bold"><Compass size={18} className="text-mustard-600" /> Strategy for my trip</h2>
          <div>
            <label className="label" htmlFor="s-dest">Destination</label>
            <select id="s-dest" className="input" value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })}>
              {dests.map((d) => <option key={d.slug} value={d.slug}>{d.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="s-origin">Flying from</label>
            <input id="s-origin" className="input" value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value })} placeholder="e.g. Delhi, Mumbai, BLR" maxLength={60} />
          </div>
          <div>
            <label className="label" htmlFor="s-date">Travel date</label>
            <input id="s-date" type="date" min={minDate} className="input" value={form.travel_date} onChange={(e) => setForm({ ...form, travel_date: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="label" htmlFor="s-nights">Nights</label>
              <input id="s-nights" type="number" min={1} max={30} className="input" value={form.nights} onChange={(e) => setForm({ ...form, nights: +e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="s-adults">People</label>
              <input id="s-adults" type="number" min={1} max={9} className="input" value={form.adults} onChange={(e) => setForm({ ...form, adults: +e.target.value })} />
            </div>
          </div>
          {error && <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
          <button className="btn-primary w-full" disabled={busy}>{busy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />} Get my strategy</button>
        </form>

        <div className="card p-5 lg:col-span-3">
          <h2 className="text-lg font-bold">Sara's recommendations</h2>
          <div className="mt-4">
            {advice ? <Suggestions items={advice} /> : <p className="text-sm text-ink-500">Pick a destination and dates. Add a date and origin to unlock fare-timing, departure-time and nearby-airport strategies.</p>}
          </div>
        </div>

        {/* Best time */}
        <div className="card p-5 lg:col-span-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-bold">Best time to visit</h2>
            <select className="input w-auto py-2" value={slug} onChange={(e) => setSlug(e.target.value)} aria-label="Destination">
              {dests.map((d) => <option key={d.slug} value={d.slug}>{d.name}, {d.state}</option>)}
            </select>
          </div>
          {best && (
            <div className="mt-5">
              <MonthStrip months={best.months} />
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div>
                  <div className="label">Best value months</div>
                  <p className="text-sm font-semibold">{best.best_value_months.join(", ") || "—"}</p>
                  {best.permit && <p className="mt-3 flex gap-2 rounded-lg bg-mustard-50 p-2.5 text-[13px] text-mustard-800"><ShieldCheck size={16} className="shrink-0" /> {best.permit}</p>}
                </div>
                <div>
                  <div className="label">Local tips</div>
                  <ul className="list-disc space-y-1 pl-5 text-sm text-ink-600">{best.tips.map((t: string) => <li key={t}>{t}</li>)}</ul>
                </div>
              </div>
              <p className="mt-3 text-[11px] text-ink-400">Bar height = how good the month is (1–5). "peak" = busiest and priciest. ★ = festival month.</p>
            </div>
          )}
        </div>

        {/* Where to go */}
        <div className="card p-5 lg:col-span-5">
          <h2 className="text-lg font-bold">Where to go in…</h2>
          <div className="mt-4 flex flex-wrap gap-1.5">
            {MONTHS.map((m, i) => (
              <button key={m} onClick={() => setMonth(i + 1)}
                className={cx("rounded-full px-3.5 py-1.5 text-sm font-semibold transition", month === i + 1 ? "bg-ink-950 text-mustard-400" : "bg-ink-100 hover:bg-ink-200")}>
                {m}
              </button>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {INTERESTS.map((it) => (
              <button key={it || "all"} onClick={() => setInterest(it)}
                className={cx("chip capitalize", interest === it && "border-ink-950 bg-mustard-200 text-ink-950")}>
                {it || "All interests"}
              </button>
            ))}
          </div>
          {where && (
            <>
              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {where.picks.map((p: Card, i: number) => (
                  <div key={p.slug} className="rounded-2xl bg-ink-950 p-4 text-cream">
                    <div className="flex items-center justify-between">
                      <span className="font-display text-2xl font-extrabold text-mustard-500">{String(i + 1).padStart(2, "0")}</span>
                      <span className="text-xs text-mustard-400">{"★".repeat(p.rating)}</span>
                    </div>
                    <div className="mt-3 font-semibold">{p.name}</div>
                    <div className="text-xs text-ink-400">{p.state} · {p.peak ? "peak season" : "good value"}</div>
                  </div>
                ))}
                {where.picks.length === 0 && <p className="text-sm text-ink-500">No great matches for this filter — try another interest.</p>}
              </div>
              {where.avoid.length > 0 && <p className="mt-4 text-sm text-ink-500"><span className="font-semibold text-ink-800">Better to avoid:</span> {where.avoid.join(", ")}</p>}
              {where.peaks?.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {where.peaks.map((pk: Card) => (
                    <span key={pk.name + pk.start} className="rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-red-700">
                      {pk.name}: {day(pk.start)} – {day(pk.end)} · fares ~+{pk.fare_increase_pct}%
                    </span>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
