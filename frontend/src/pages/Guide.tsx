import { BookOpen, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Card } from "../lib/api";
import { cx } from "../lib/format";
import { PageHeader } from "./Strategist";

const TOPICS = [
  { id: "", label: "All topics" },
  { id: "permit", label: "Permits" },
  { id: "train", label: "Trains & IRCTC" },
  { id: "pilgrimage temple char dham", label: "Pilgrimage" },
  { id: "flight airport baggage", label: "Flights" },
  { id: "fog monsoon weather", label: "Weather risks" },
  { id: "scam safety", label: "Safety" },
  { id: "app help payment", label: "Using the app" },
];

export default function Guide() {
  const [q, setQ] = useState("");
  const [topic, setTopic] = useState("");
  const [results, setResults] = useState<Card[] | null>(null);

  useEffect(() => {
    const query = [q, topic].filter(Boolean).join(" ");
    const id = setTimeout(() => {
      api<{ results: Card[] }>(`/api/guide${query ? `?q=${encodeURIComponent(query)}` : ""}`)
        .then((r) => setResults(r.results)).catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(id);
  }, [q, topic]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <PageHeader title="Travel Guide" text="Permits, train rules, pilgrimage registrations, safety and app help — with sources." />
      <div className="card mb-4 flex flex-wrap items-center gap-3 p-4">
        <div className="relative min-w-[220px] flex-1">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-400" />
          <input className="input pl-10" placeholder="Search, e.g. “Tawang permit” or “Tatkal timing”" value={q} onChange={(e) => setQ(e.target.value)} maxLength={200} />
        </div>
        <select className="input w-auto" value={topic} onChange={(e) => setTopic(e.target.value)} aria-label="Topic">
          {TOPICS.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
        </select>
      </div>
      <div className="space-y-3">
        {results?.length === 0 && <p className="text-sm text-ink-500">Nothing found. Try different words, or ask Sara.</p>}
        {results?.map((r) => (
          <article key={r.id} className="card p-5">
            <h2 className="flex items-center gap-2 font-bold"><BookOpen size={16} className="text-mustard-600" /> {r.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-ink-700">{r.text}</p>
            <p className={cx("mt-2 text-[11px] text-ink-400")}>Source: {r.source} · verified {r.verified}</p>
          </article>
        ))}
      </div>
      <p className="mt-6 text-[11px] text-ink-400">Rules change often — always confirm on the official source before travelling.</p>
    </div>
  );
}
