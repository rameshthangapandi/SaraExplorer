import { ArrowLeft, ArrowRight, Clock, Coffee, ExternalLink, Hotel, Landmark, Leaf, Loader2, LocateFixed, MapPin, ShieldCheck, Utensils } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { MonthStrip } from "../components/cards/Cards";
import MapView, { type Pin } from "../components/MapView";
import { api, type Card } from "../lib/api";
import { cx, day } from "../lib/format";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const INTERESTS = ["", "beach", "mountains", "heritage", "spiritual", "adventure", "honeymoon", "food", "nature", "offbeat"];

function Photo({ src, alt, className }: { src?: string | null; alt: string; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div className={cx("grid place-items-center bg-gradient-to-br from-mustard-400 to-mustard-700 text-ink-950", className)}>
        <MapPin size={28} />
      </div>
    );
  }
  return <img src={src} alt={alt} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} className={cx("object-cover", className)} />;
}

export function ExploreList() {
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [interest, setInterest] = useState("");
  const [data, setData] = useState<{ month: string; destinations: Card[] } | null>(null);

  useEffect(() => {
    setData(null);
    api<{ month: string; destinations: Card[] }>(`/api/explore/destinations?month=${month}${interest ? `&interest=${interest}` : ""}`)
      .then(setData).catch(() => setData({ month: MONTHS[month - 1], destinations: [] }));
  }, [month, interest]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold sm:text-4xl">Explore India</h1>
        <p className="mt-1 text-ink-500">Destinations ranked for the month you travel. Open one for photos, map, places to eat and things to see.</p>
      </div>
      <div className="card mb-6 flex flex-wrap items-end gap-4 p-4">
        <label className="min-w-[160px] flex-1">
          <span className="label">Travel month</span>
          <select className="input" value={month} onChange={(e) => setMonth(+e.target.value)}>
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </select>
        </label>
        <label className="min-w-[160px] flex-1">
          <span className="label">Interest</span>
          <select className="input capitalize" value={interest} onChange={(e) => setInterest(e.target.value)}>
            {INTERESTS.map((i) => <option key={i || "all"} value={i}>{i || "All interests"}</option>)}
          </select>
        </label>
      </div>

      {!data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => <div key={i} className="h-64 animate-pulse rounded-2xl bg-ink-100" />)}
        </div>
      ) : data.destinations.length === 0 ? (
        <p className="text-ink-500">No destinations match this interest.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.destinations.map((d) => (
            <Link key={d.slug} to={`/app/explore/${d.slug}`} className="group card overflow-hidden transition hover:-translate-y-0.5 hover:shadow-lg">
              <div className="relative h-44 overflow-hidden">
                <Photo src={d.image} alt={d.name} className="h-full w-full transition duration-500 group-hover:scale-105" />
                <div className="absolute left-3 top-3 flex gap-1.5">
                  <span className={cx("rounded-full px-2.5 py-1 text-[11px] font-bold",
                    d.rating >= 4 ? "bg-mustard-500 text-ink-950" : d.rating === 3 ? "bg-white text-ink-900" : "bg-ink-950 text-cream")}>
                    {d.rating >= 5 ? "Ideal" : d.rating === 4 ? "Good" : d.rating === 3 ? "Okay" : "Not ideal"} in {data.month.slice(0, 3)}
                  </span>
                  {d.peak && <span className="rounded-full bg-ink-950/80 px-2.5 py-1 text-[11px] font-bold text-cream">Peak season</span>}
                </div>
              </div>
              <div className="flex items-center justify-between p-4">
                <div>
                  <div className="font-display text-lg font-bold">{d.name}</div>
                  <div className="text-xs text-ink-500">{d.state}{d.permit ? " · permit needed" : ""}</div>
                </div>
                <span className="text-mustard-600">{"★".repeat(d.rating)}<span className="text-ink-200">{"★".repeat(5 - d.rating)}</span></span>
              </div>
            </Link>
          ))}
        </div>
      )}
      <p className="mt-6 text-[11px] text-ink-400">Photos: Wikipedia / Wikimedia Commons. Ratings show how suitable each month usually is (weather, crowds).</p>
    </div>
  );
}

const TABS: { id: string; label: string; icon: ReactNode }[] = [
  { id: "attractions", label: "Things to see", icon: <Landmark size={15} /> },
  { id: "restaurants", label: "Restaurants", icon: <Utensils size={15} /> },
  { id: "cafes", label: "Cafes", icon: <Coffee size={15} /> },
  { id: "stays", label: "Stays", icon: <Hotel size={15} /> },
];

const km = (m: number) => (m < 1000 ? `${m} m` : `${(m / 1000).toFixed(1)} km`);

export function Destination() {
  const { slug } = useParams();
  const [d, setD] = useState<Card | null>(null);
  const [tab, setTab] = useState("attractions");
  const [here, setHere] = useState<{ lat: number; lon: number } | null>(null);
  const [nearby, setNearby] = useState<{ items: Card[]; source: string } | null>(null);
  const [active, setActive] = useState<number | null>(null);
  const [geoError, setGeoError] = useState("");

  useEffect(() => {
    api<Card>(`/api/explore/destinations/${slug}`).then(setD).catch(() => setD({ type: "error", error: true }));
  }, [slug]);

  const center = here ?? (d && !d.error ? { lat: d.lat, lon: d.lon } : null);

  useEffect(() => {
    if (!center) return;
    setNearby(null);
    setActive(null);
    api<{ items: Card[]; source: string }>(`/api/explore/nearby?lat=${center.lat}&lon=${center.lon}&kind=${tab}`)
      .then(setNearby).catch(() => setNearby({ items: [], source: "" }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center?.lat, center?.lon, tab]);

  const locate = () => {
    setGeoError("");
    if (here) return setHere(null);
    navigator.geolocation.getCurrentPosition(
      (p) => setHere({ lat: p.coords.latitude, lon: p.coords.longitude }),
      () => setGeoError("Location access was blocked or unavailable."),
      { enableHighAccuracy: false, timeout: 10000 },
    );
  };

  if (!d) return <div className="grid h-64 place-items-center"><Loader2 className="animate-spin text-mustard-600" /></div>;
  if (d.error) return <div className="p-8">Destination not found. <Link to="/app/explore" className="underline">Back to Explore</Link></div>;

  const pins: Pin[] = [
    ...(here ? [{ lat: here.lat, lon: here.lon, title: "You are here", kind: "me" }] : [{ lat: d.lat, lon: d.lon, title: d.name, kind: "center" }]),
    ...(nearby?.items ?? []).map((p) => ({ lat: p.lat, lon: p.lon, title: p.name, subtitle: p.cuisine ?? p.description ?? undefined, kind: tab, href: p.maps_url ?? p.url })),
  ];
  const offset = 1;

  return (
    <div className="pb-10">
      <div className="relative h-72 overflow-hidden bg-ink-950 sm:h-96">
        <Photo src={d.summary?.image} alt={d.name} className="h-full w-full opacity-80" />
        <div className="absolute inset-0 bg-gradient-to-t from-ink-950 via-ink-950/30 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 mx-auto max-w-6xl px-4 pb-6 sm:px-6">
          <Link to="/app/explore" className="mb-3 inline-flex items-center gap-1 text-sm text-ink-200 hover:text-cream"><ArrowLeft size={14} /> All destinations</Link>
          <h1 className="text-4xl font-extrabold text-cream sm:text-5xl">{d.name}</h1>
          <p className="text-mustard-400">{d.state} · {d.tags.join(" · ")}</p>
        </div>
      </div>

      <div className="mx-auto max-w-6xl space-y-6 px-4 pt-6 sm:px-6">
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="card p-5">
            <p className="leading-relaxed text-ink-700">{d.summary?.extract || "A wonderful destination in India."}</p>
            {d.summary?.url && <a href={d.summary.url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-mustard-700">Read more on Wikipedia <ExternalLink size={13} /></a>}
            <div className="mt-5">
              <div className="label">Best time to visit</div>
              <MonthStrip months={d.best_time.months} />
            </div>
          </div>
          <div className="space-y-4">
            <Link to={`/app?to=${d.slug}`} className="btn-primary w-full py-3">Plan a trip to {d.name} <ArrowRight size={16} /></Link>
            <div className="card space-y-3 p-4 text-sm">
              <div><div className="label">Best value months</div>{d.best_time.best_value_months.join(", ") || "—"}</div>
              <div><div className="label">Getting there</div>{[...d.airports.map((a: Card) => `✈ ${a.code}`), ...d.stations.map((s: Card) => `🚆 ${s.name}`)].join(" · ") || "By road"}</div>
              {d.best_time.permit && <div className="flex gap-2 rounded-lg bg-mustard-50 p-2.5 text-[13px] text-mustard-800"><ShieldCheck size={16} className="shrink-0" /> {d.best_time.permit}</div>}
              {d.closed.length > 0 && <div><div className="label">Closed days</div>{d.closed.map((c: Card) => `${c.place}: ${c.day}`).join(" · ")}</div>}
            </div>
          </div>
        </div>

        {d.forecast && (
          <div className="card p-4">
            <h2 className="mb-3 font-bold">Next 7 days <span className="text-xs font-normal text-ink-400">· live forecast, Open-Meteo</span></h2>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {d.forecast.map((f: Card) => (
                <div key={f.date} className="min-w-[96px] rounded-xl border border-ink-100 p-2.5 text-center">
                  <div className="text-[11px] font-semibold text-ink-500">{day(f.date)}</div>
                  <div className="mt-1 text-xs">{f.summary}</div>
                  <div className="font-display font-bold">{Math.round(f.max_c)}° <span className="text-ink-400">{Math.round(f.min_c)}°</span></div>
                  <div className="text-[11px] text-ink-500">{f.rain_chance ?? 0}% rain</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          {d.festivals.length > 0 && (
            <div className="card p-4">
              <h2 className="mb-2 font-bold">Festivals & events</h2>
              <ul className="space-y-2 text-sm">{d.festivals.map((f: Card) => <li key={f.name}><b>{f.name}</b> <span className="text-ink-500">({f.months.join(", ")})</span><div className="text-ink-600">{f.note}</div></li>)}</ul>
            </div>
          )}
          <div className="card p-4">
            <h2 className="mb-2 font-bold">Local tips</h2>
            <ul className="list-disc space-y-1 pl-5 text-sm text-ink-600">{d.best_time.tips.map((t: string) => <li key={t}>{t}</li>)}</ul>
          </div>
        </div>

        {/* Nearby */}
        <div className="card p-4 sm:p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-xl font-bold">Around {here ? "you" : d.name}</h2>
            <button onClick={locate} className={cx("btn-outline px-4 py-2", here && "border-ink-950 bg-mustard-100")}>
              <LocateFixed size={15} /> {here ? `Back to ${d.name}` : "Near me"}
            </button>
          </div>
          {geoError && <p className="mb-3 text-sm text-red-600">{geoError}</p>}
          <div className="mb-4 flex flex-wrap gap-2">
            {TABS.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={cx("inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold transition",
                  tab === t.id ? "bg-ink-950 text-mustard-400" : "bg-ink-100 hover:bg-ink-200")}>
                {t.icon} {t.label}
              </button>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
            {center && <MapView center={center} pins={pins} zoom={tab === "attractions" ? 12 : 14} activeIndex={active === null ? null : active + offset} className="h-80 lg:h-[520px]" />}
            <div className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
              {!nearby ? (
                <div className="flex items-center gap-2 text-sm text-ink-500"><Loader2 size={16} className="animate-spin" /> Finding places…</div>
              ) : nearby.items.length === 0 ? (
                <p className="text-sm text-ink-500">No places found nearby right now. Try another tab or again in a minute.</p>
              ) : nearby.items.map((p, i) => (
                <div key={`${p.name}-${i}`} onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)}
                  className={cx("flex gap-3 rounded-xl border p-2.5 transition", active === i ? "border-ink-950" : "border-ink-100")}>
                  {tab === "attractions" ? (
                    <Photo src={p.image} alt={p.name} className="size-20 shrink-0 rounded-lg" />
                  ) : (
                    <div className="grid size-20 shrink-0 place-items-center rounded-lg bg-ink-950 text-mustard-400">
                      {tab === "restaurants" ? <Utensils size={22} /> : tab === "cafes" ? <Coffee size={22} /> : <Hotel size={22} />}
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-semibold">{p.name}</div>
                    <div className="truncate text-xs text-ink-500">{p.description ?? (p.cuisine ? `${p.cuisine}` : tab === "stays" ? `Hotel${p.stars ? ` · ${p.stars}★` : ""}` : "Cuisine not listed")}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px]">
                      <span className="chip"><MapPin size={11} /> {km(p.distance_m)}</span>
                      {p.vegetarian && <span className="chip border-emerald-200 text-emerald-700"><Leaf size={11} /> Veg</span>}
                      {p.opening_hours && <span className="chip max-w-[180px] truncate"><Clock size={11} /> {p.opening_hours}</span>}
                    </div>
                    <a href={p.maps_url ?? p.url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-mustard-700 hover:underline">
                      {tab === "attractions" ? "Read on Wikipedia" : "Photos & reviews on Google Maps"} <ExternalLink size={11} />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <p className="mt-3 text-[11px] text-ink-400">
            {tab === "attractions" ? "Places and photos from Wikipedia." : "Places from © OpenStreetMap contributors. Photos and ratings open in Google Maps."}
          </p>
        </div>
      </div>
    </div>
  );
}
