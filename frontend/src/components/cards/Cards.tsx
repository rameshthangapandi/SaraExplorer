import {
  AlertTriangle, BookOpen, CalendarDays, Clock, CloudSun, Compass, Hotel, IndianRupee, Lightbulb, MapPin, Plane,
  ShieldCheck, Sparkles, Star, Ticket, TrainFront,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import type { Card } from "../../lib/api";
import { cx, day, duration, inr, time } from "../../lib/format";
import ConsentCard from "./ConsentCard";
import { RideResults } from "../../pages/Rides";

type Send = (text: string) => void;

function Shell({ icon, title, children, badge }: { icon: ReactNode; title?: string; children: ReactNode; badge?: string }) {
  return (
    <div className="card animate-rise overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-ink-100 bg-ink-950 px-4 py-2.5 text-cream">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <span className="text-mustard-400">{icon}</span>
          {title}
        </div>
        {badge && <span className="rounded-full bg-mustard-500 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-ink-950">{badge}</span>}
      </div>
      <div className="p-3 sm:p-4">{children}</div>
    </div>
  );
}

function ShowMore<T>({ items, initial = 3, render }: { items: T[]; initial?: number; render: (item: T, i: number) => ReactNode }) {
  const [all, setAll] = useState(false);
  const shown = all ? items : items.slice(0, initial);
  return (
    <>
      <div className="space-y-2">{shown.map(render)}</div>
      {items.length > initial && (
        <button className="mt-2 text-xs font-semibold text-mustard-700 hover:underline" onClick={() => setAll(!all)}>
          {all ? "Show fewer" : `Show all ${items.length} options`}
        </button>
      )}
    </>
  );
}

function ChooseButton({ onClick }: { onClick: () => void }) {
  return (
    <button onClick={onClick} className="rounded-full bg-ink-950 px-3.5 py-1.5 text-xs font-semibold text-cream transition hover:bg-mustard-500 hover:text-ink-950">
      Choose
    </button>
  );
}

function Flights({ card, onSend }: { card: Card; onSend: Send }) {
  return (
    <Shell icon={<Plane size={16} />} title={`${card.title} · ${day(card.date)}`} >
      <ShowMore
        items={card.options}
        render={(o: Card) => (
          <div key={o.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-ink-100 px-3 py-2.5 hover:border-ink-300">
            <div className="min-w-[110px]">
              <div className="text-sm font-semibold">{o.airline}</div>
              <div className="text-[11px] text-ink-400">{o.flight_no} · {o.id}</div>
            </div>
            <div className="flex flex-1 items-center gap-2 text-sm">
              <span className="font-semibold">{time(o.depart)}</span>
              <span className="flex flex-1 items-center gap-1 text-[11px] text-ink-400">
                <span className="h-px flex-1 bg-ink-200" />
                {duration(o.duration_min)} · {o.stops ? `1 stop (${o.via})` : "non-stop"}
                <span className="h-px flex-1 bg-ink-200" />
              </span>
              <span className="font-semibold">{time(o.arrive)}</span>
            </div>
            <div className="text-right">
              <div className="font-display text-base font-bold">{inr(o.price_total)}</div>
              <div className="text-[11px] text-ink-400">{o.adults > 1 ? `${inr(o.price_per_person)} × ${o.adults}` : o.refundable ? "Refundable" : "Non-refundable"}</div>
            </div>
            <ChooseButton onClick={() => onSend(`I'd like flight option ${o.id} (${o.airline} ${o.flight_no}).`)} />
          </div>
        )}
      />
    </Shell>
  );
}

function availabilityStyle(status: string) {
  if (status.startsWith("AVAILABLE")) return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (status.startsWith("RAC")) return "bg-mustard-50 text-mustard-800 border-mustard-200";
  return "bg-red-50 text-red-700 border-red-200";
}

function Trains({ card, onSend }: { card: Card; onSend: Send }) {
  return (
    <Shell icon={<TrainFront size={16} />} title={`${card.title} · ${day(card.date)}`}>
      <ShowMore
        items={card.options}
        initial={4}
        render={(o: Card) => (
          <div key={o.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-ink-100 px-3 py-2.5 hover:border-ink-300">
            <div className="min-w-[180px] flex-1">
              <div className="text-sm font-semibold">{o.train_name}</div>
              <div className="text-[11px] text-ink-400">#{o.train_no} · {time(o.depart)} → {time(o.arrive)} · {duration(o.duration_min)} · {o.id}</div>
            </div>
            <span className="chip">{o.class}</span>
            <span className={cx("rounded-full border px-2.5 py-0.5 text-[11px] font-semibold", availabilityStyle(o.availability))}>
              {o.availability}
              {o.availability.startsWith("WL") && ` · ${Math.round(o.confirm_chance * 100)}% likely`}
            </span>
            <div className="font-display text-base font-bold">{inr(o.price_total)}</div>
            <ChooseButton onClick={() => onSend(`I'd like train option ${o.id} (${o.train_no}, ${o.class}).`)} />
          </div>
        )}
      />
    </Shell>
  );
}

function Hotels({ card, onSend }: { card: Card; onSend: Send }) {
  return (
    <Shell icon={<Hotel size={16} />} title={card.title}>
      <ShowMore
        items={card.options}
        render={(o: Card) => (
          <div key={o.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-ink-100 px-3 py-2.5 hover:border-ink-300">
            <div className="min-w-[200px] flex-1">
              <div className="text-sm font-semibold">{o.hotel}</div>
              <div className="mt-0.5 flex items-center gap-2 text-[11px] text-ink-500">
                <span className="text-mustard-600">{"★".repeat(o.stars)}</span>
                <span className="flex items-center gap-0.5"><Star size={11} className="fill-ink-900" /> {o.rating} ({o.reviews})</span>
                <span>· {o.nights} night{o.nights > 1 ? "s" : ""} · {o.rooms} room{o.rooms > 1 ? "s" : ""}</span>
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {o.amenities.map((a: string) => <span key={a} className="chip">{a}</span>)}
              </div>
            </div>
            <div className="text-right">
              <div className="font-display text-base font-bold">{inr(o.price_total)}</div>
              <div className="text-[11px] text-ink-400">{inr(o.price_per_night)}/night</div>
              {o.free_cancellation_until && <div className="text-[11px] font-medium text-emerald-700">Free cancel till {day(o.free_cancellation_until)}</div>}
            </div>
            <ChooseButton onClick={() => onSend(`I'd like hotel option ${o.id} (${o.hotel}).`)} />
          </div>
        )}
      />
    </Shell>
  );
}

const CATEGORY_ICON: Record<string, ReactNode> = {
  money: <IndianRupee size={14} />,
  time: <Clock size={14} />,
  experience: <Sparkles size={14} />,
  risk: <AlertTriangle size={14} />,
};

export function Suggestions({ items }: { items: Card[] }) {
  if (!items.length) return <p className="text-sm text-ink-500">No specific suggestions for these dates — looks like a solid plan.</p>;
  return (
    <ol className="space-y-2">
      {items.map((s, i) => (
        <li key={i} className="flex gap-3 rounded-xl border border-ink-100 p-3">
          <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-mustard-100 text-mustard-800">{CATEGORY_ICON[s.category] ?? <Lightbulb size={14} />}</span>
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold">{s.title}</span>
              {s.saving_inr ? <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700">Save {inr(s.saving_inr)}</span> : null}
              <span className="chip capitalize">{s.category}</span>
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-600">{s.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function Strategy({ card }: { card: Card }) {
  return (
    <Shell icon={<Compass size={16} />} title={card.title} badge="Strategist">
      <Suggestions items={card.suggestions} />
    </Shell>
  );
}

export function MonthStrip({ months }: { months: Card[] }) {
  return (
    <div className="grid grid-cols-6 gap-1.5 sm:grid-cols-12">
      {months.map((m) => (
        <div key={m.month} className="text-center" title={`${m.name}: ${m.rating}/5${m.peak ? " · peak season" : ""}${m.festivals.length ? " · " + m.festivals.join(", ") : ""}`}>
          <div className="flex h-16 items-end overflow-hidden rounded-lg bg-ink-100">
            <div
              className={cx("w-full rounded-lg transition-all", m.rating >= 5 ? "bg-mustard-500" : m.rating === 4 ? "bg-mustard-300" : m.rating === 3 ? "bg-mustard-200" : "bg-ink-300")}
              style={{ height: `${m.rating * 20}%` }}
            />
          </div>
          <div className="mt-1 text-[11px] font-semibold">{m.name.slice(0, 3)}</div>
          <div className="h-3 text-[10px] leading-3 text-ink-400">{m.peak ? "peak" : m.festivals.length ? "★" : ""}</div>
        </div>
      ))}
    </div>
  );
}

function BestTime({ card }: { card: Card }) {
  return (
    <Shell icon={<CalendarDays size={16} />} title={`Best time for ${card.destination}`} badge="Strategist">
      <MonthStrip months={card.months} />
      {card.best_value_months?.length > 0 && (
        <p className="mt-3 text-sm"><span className="font-semibold">Best value:</span> {card.best_value_months.join(", ")}</p>
      )}
      {card.permit && <p className="mt-2 flex gap-2 rounded-lg bg-mustard-50 p-2 text-[13px] text-mustard-800"><ShieldCheck size={16} className="shrink-0" /> {card.permit}</p>}
      <ul className="mt-2 list-disc space-y-0.5 pl-5 text-[13px] text-ink-600">
        {card.tips.map((t: string) => <li key={t}>{t}</li>)}
      </ul>
    </Shell>
  );
}

function Where({ card }: { card: Card }) {
  return (
    <Shell icon={<MapPin size={16} />} title={card.title} badge="Strategist">
      <div className="grid gap-2 sm:grid-cols-2">
        {card.picks.map((p: Card, i: number) => (
          <div key={p.slug} className="flex items-center gap-3 rounded-xl border border-ink-100 p-3">
            <span className="font-display text-2xl font-extrabold text-mustard-500">{i + 1}</span>
            <div>
              <div className="text-sm font-semibold">{p.name} <span className="text-mustard-600">{"★".repeat(p.rating)}</span></div>
              <div className="text-[11px] text-ink-500">{p.state}{p.peak ? " · peak season" : " · good value"}</div>
            </div>
          </div>
        ))}
      </div>
      {card.avoid?.length > 0 && <p className="mt-3 text-[13px] text-ink-500"><span className="font-semibold text-ink-800">Better to avoid:</span> {card.avoid.join(", ")}</p>}
    </Shell>
  );
}

function Weather({ card }: { card: Card }) {
  return (
    <Shell icon={<CloudSun size={16} />} title={card.title} badge="Live · Open-Meteo">
      <div className="flex gap-2 overflow-x-auto pb-1">
        {card.days.map((d: Card) => (
          <div key={d.date} className="min-w-[92px] rounded-xl border border-ink-100 p-2.5 text-center">
            <div className="text-[11px] font-semibold text-ink-500">{day(d.date)}</div>
            <div className="mt-1 text-xs font-medium">{d.summary}</div>
            <div className="mt-1 font-display text-sm font-bold">{Math.round(d.max_c)}° <span className="text-ink-400">{Math.round(d.min_c)}°</span></div>
            <div className="text-[11px] text-ink-500">{d.rain_chance ?? 0}% rain</div>
          </div>
        ))}
      </div>
    </Shell>
  );
}

function Knowledge({ card }: { card: Card }) {
  return (
    <Shell icon={<BookOpen size={16} />} title={card.title}>
      <div className="space-y-2">
        {card.results.map((r: Card) => (
          <div key={r.id} className="rounded-xl border border-ink-100 p-3">
            <div className="text-sm font-semibold">{r.title}</div>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-600">{r.text}</p>
            <div className="mt-1.5 text-[11px] text-ink-400">Source: {r.source} · verified {r.verified}</div>
          </div>
        ))}
      </div>
    </Shell>
  );
}

export function BookingRow({ b, action }: { b: Card; action?: ReactNode }) {
  const icon = b.kind === "flight" ? <Plane size={18} /> : b.kind === "train" ? <TrainFront size={18} /> : <Hotel size={18} />;
  return (
    <div className="ticket flex items-stretch border border-ink-100">
      <div className="grid w-14 shrink-0 place-items-center bg-ink-950 text-mustard-400">{icon}</div>
      <div className="flex flex-1 flex-wrap items-center gap-3 px-4 py-3">
        <div className="min-w-[180px] flex-1">
          <div className="text-sm font-semibold">{b.title}</div>
          <div className="text-[11px] text-ink-500">Ref <span className="font-mono font-semibold text-ink-900">{b.reference}</span> · {day(b.created_at)}</div>
        </div>
        <span className={cx("rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase",
          b.status === "confirmed" ? "bg-emerald-50 text-emerald-700" : b.status === "waitlisted" ? "bg-mustard-100 text-mustard-800" : "bg-ink-100 text-ink-500")}>
          {b.status}
        </span>
        <div className="font-display font-bold">{inr(b.amount_inr)}</div>
        {action}
      </div>
    </div>
  );
}

function Bookings({ card }: { card: Card }) {
  return (
    <Shell icon={<Ticket size={16} />} title={card.title}>
      <div className="space-y-2">{card.bookings.map((b: Card) => <BookingRow key={b.id} b={b} />)}</div>
    </Shell>
  );
}

function AutoPlan({ card, onSend }: { card: Card; onSend: Send }) {
  if (card.status !== "ok") {
    return (
      <Shell icon={<AlertTriangle size={16} />} title="No plan fits these conditions" badge="Solver">
        <p className="text-sm text-ink-700">{card.reasons.join(" ")}</p>
      </Shell>
    );
  }
  const legs: [string, Card | null][] = [["Onward", card.plan.out], ["Stay", card.plan.stay], ["Return", card.plan.back]];
  return (
    <Shell icon={<Sparkles size={16} />} title="Best trip within your conditions" badge="Solver">
      <div className="space-y-2">
        {legs.filter(([, o]) => o).map(([label, o]) => (
          <div key={label} className="flex items-center gap-3 rounded-xl border border-ink-100 px-3 py-2.5">
            <span className="w-16 text-[11px] font-semibold uppercase tracking-wider text-ink-400">{label}</span>
            <span className="flex-1 text-sm font-semibold">{o!.hotel ?? o!.airline ?? o!.train_name}
              <span className="ml-1 text-[11px] font-normal text-ink-500">{o!.hotel ? `${o!.nights} nights` : `${time(o!.depart)} · ${o!.flight_no ?? o!.class}`}</span>
            </span>
            <span className="font-display font-bold">{inr(o!.price_total)}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm"><span className="text-ink-500">Total</span> <b className="font-display text-lg">{inr(card.total)}</b>
          {card.budget_total && <span className="ml-1 text-xs text-emerald-700">within ₹{Number(card.budget_total).toLocaleString("en-IN")}</span>}
        </div>
        <button onClick={() => onSend(`Book this plan: ${card.option_ids.join(", ")}`)} className="btn-dark px-4 py-2">Book this plan</button>
      </div>
      {card.why?.length > 0 && <p className="mt-2 text-xs text-emerald-800">Why it suits you: {card.why.join("; ")}.</p>}
      <p className="mt-2 text-[11px] text-ink-400">Checked {card.candidates_checked} combinations against all your conditions.</p>
    </Shell>
  );
}

export default function CardRenderer({ card, onSend }: { card: Card; onSend: Send }) {
  switch (card.type) {
    case "autoplan": return <AutoPlan card={card} onSend={onSend} />;
    case "rides": return <Shell icon={<MapPin size={16} />} title="Local rides compared" badge="Estimates"><RideResults data={card} /></Shell>;
    case "flights": return <Flights card={card} onSend={onSend} />;
    case "trains": return <Trains card={card} onSend={onSend} />;
    case "hotels": return <Hotels card={card} onSend={onSend} />;
    case "strategy": return <Strategy card={card} />;
    case "best_time": return <BestTime card={card} />;
    case "where": return <Where card={card} />;
    case "weather": return <Weather card={card} />;
    case "knowledge": return <Knowledge card={card} />;
    case "consent": return <ConsentCard card={card} />;
    case "bookings": return <Bookings card={card} />;
    default: return null;
  }
}
