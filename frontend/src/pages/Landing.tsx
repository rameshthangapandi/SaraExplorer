import {
  ArrowRight, BadgeCheck, CalendarRange, Compass, Fingerprint, Lock, Mic, MountainSnow, Palmtree, Plane, Radar,
  ShieldCheck, Sparkles, TrainFront, Waves,
} from "lucide-react";
import { Link } from "react-router-dom";
import Logo from "../components/Logo";
import SaraAvatar from "../components/SaraAvatar";
import { useAuth } from "../lib/auth";

const FEATURES = [
  { icon: <Sparkles size={20} />, title: "Plan by tapping — or chatting", text: "Pick from simple dropdowns, or just tell Sara where, when and who." },
  { icon: <Compass size={20} />, title: "The Strategist", text: "When to book, when to go, which airport, which day — strategies that save money and stress." },
  { icon: <BadgeCheck size={20} />, title: "Pay by UPI, booked on receipt", text: "Approve the exact total, pay by UPI QR, and your trip is booked once the money is received." },
  { icon: <Mic size={20} />, title: "Speak, don't type", text: "Tap the mic and talk to Sara in English or Hindi." },
  { icon: <TrainFront size={20} />, title: "Made for Indian rails", text: "Waitlist confirmation chances, quotas, Tatkal timing and fog-season buffers." },
  { icon: <Radar size={20} />, title: "Maps, photos & places", text: "Explore destinations with photos, maps, things to see and places to eat nearby." },
];

const SEASONS = [
  { month: "Jan", place: "Rann of Kutch", icon: <Sparkles size={18} />, note: "White desert under a full moon" },
  { month: "Mar", place: "Srinagar", icon: <Palmtree size={18} />, note: "Tulip festival in bloom" },
  { month: "Jul", place: "Leh–Ladakh", icon: <MountainSnow size={18} />, note: "Clear skies, all passes open" },
  { month: "Oct", place: "Gangtok", icon: <MountainSnow size={18} />, note: "Crisp views of Kanchenjunga" },
  { month: "Dec", place: "Alleppey", icon: <Waves size={18} />, note: "Houseboats on calm backwaters" },
];

const STEPS = [
  { n: "01", title: "Ask", text: "\"Plan 5 days in Kerala with my parents under ₹50k.\"" },
  { n: "02", title: "Strategise", text: "Sara checks seasons, fares, closed days and permits." },
  { n: "03", title: "Approve & pay", text: "One approval card with the full price, then pay by UPI." },
  { n: "04", title: "Travel", text: "Your references, bookings and plan — all in one place." },
];

export default function Landing() {
  const { user } = useAuth();
  const cta = user ? "/app" : "/register";

  return (
    <div className="min-h-screen bg-cream">
      {/* Hero */}
      <header className="relative overflow-hidden bg-ink-950 text-cream">
        <div className="bg-grid absolute inset-0" aria-hidden />
        <div className="absolute -right-40 -top-40 size-[520px] rounded-full bg-mustard-500/20 blur-3xl" aria-hidden />
        <nav className="relative mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
          <Logo dark />
          <div className="flex items-center gap-2">
            <a href="#features" className="hidden px-3 text-sm text-ink-300 hover:text-cream sm:block">Features</a>
            <a href="#security" className="hidden px-3 text-sm text-ink-300 hover:text-cream sm:block">Security</a>
            {user ? (
              <Link to="/app" className="btn-primary">Open app <ArrowRight size={16} /></Link>
            ) : (
              <>
                <Link to="/login" className="btn px-4 text-cream hover:bg-ink-800">Log in</Link>
                <Link to="/register" className="btn-primary">Get started</Link>
              </>
            )}
          </div>
        </nav>

        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-10 lg:grid-cols-[1.1fr_0.9fr] lg:pt-16">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-mustard-500/40 bg-mustard-500/10 px-3 py-1 text-xs font-semibold text-mustard-300">
              <span className="size-1.5 rounded-full bg-mustard-400" /> India's agentic AI trip planner
            </span>
            <h1 className="mt-5 text-5xl font-extrabold leading-[1.02] sm:text-6xl lg:text-7xl">
              Plan India.<br />
              <span className="text-mustard-500">Ask Sara.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-300">
              Sara plans your trip, finds the smartest time to book and travel, and books it — only after you say yes.
              Flights, trains, stays, seasons and permits, all in one conversation.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to={cta} className="btn-primary px-6 py-3 text-base">Start planning free <ArrowRight size={18} /></Link>
              <a href="#how" className="btn border border-ink-600 px-6 py-3 text-base text-cream hover:border-cream">See how it works</a>
            </div>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-400">
              <span className="flex items-center gap-1.5"><ShieldCheck size={16} className="text-mustard-500" /> Consent before every booking</span>
              <span className="flex items-center gap-1.5"><Lock size={16} className="text-mustard-500" /> Booked only after payment is confirmed</span>
            </div>
          </div>

          {/* Chat preview */}
          <div className="relative">
            <div className="absolute -left-6 -top-6 animate-float"><SaraAvatar size={72} mood="happy" /></div>
            <div className="rounded-3xl border border-ink-700 bg-ink-900 p-5 shadow-2xl">
              <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-mustard-500 px-4 py-2.5 text-sm font-medium text-ink-950">
                Delhi to Goa, 2 people, early December. Best deal?
              </div>
              <div className="mt-4 space-y-3 rounded-2xl rounded-bl-md bg-ink-800 p-4 text-sm text-ink-200">
                <p>Here's my strategy for you:</p>
                <div className="flex items-start gap-2"><Plane size={16} className="mt-0.5 text-mustard-400" /> <span><b className="text-cream">Book now</b> — you're in the 3–6 week low-fare window.</span></div>
                <div className="flex items-start gap-2"><CalendarRange size={16} className="mt-0.5 text-mustard-400" /> <span>The <b className="text-cream">5:45 AM</b> flight saves ₹2,960 vs evening.</span></div>
                <div className="flex items-start gap-2"><Sparkles size={16} className="mt-0.5 text-mustard-400" /> <span>Return before <b className="text-cream">20 Dec</b> to dodge the holiday surge.</span></div>
              </div>
              <div className="ticket mt-4 bg-cream text-ink-950">
                <div className="flex items-center justify-between bg-mustard-500 px-4 py-2 text-xs font-bold uppercase tracking-wider">Approval needed <span className="font-mono">14:52</span></div>
                <div className="flex items-center justify-between px-4 py-3">
                  <span className="text-sm font-semibold">Flights + 3 nights, Goa</span>
                  <span className="font-display text-lg font-extrabold">₹24,440</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Features */}
      <section id="features" className="mx-auto max-w-6xl px-5 py-20">
        <p className="text-sm font-bold uppercase tracking-widest text-mustard-700">What Sara does</p>
        <h2 className="mt-2 max-w-2xl text-4xl font-extrabold">A travel agent, strategist and booking desk — in one chat.</h2>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="card group p-6 transition hover:-translate-y-0.5 hover:border-ink-900">
              <span className="grid size-11 place-items-center rounded-xl bg-ink-950 text-mustard-400 transition group-hover:bg-mustard-500 group-hover:text-ink-950">{f.icon}</span>
              <h3 className="mt-4 text-lg font-bold">{f.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-600">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Season strip */}
      <section className="bg-mustard-500">
        <div className="mx-auto max-w-6xl px-5 py-16">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm font-bold uppercase tracking-widest text-ink-800">The Strategist knows the seasons</p>
              <h2 className="mt-2 text-4xl font-extrabold text-ink-950">Right place. Right month.</h2>
            </div>
            <Link to={cta} className="btn-dark">Find my month <ArrowRight size={16} /></Link>
          </div>
          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {SEASONS.map((s) => (
              <div key={s.month} className="rounded-2xl bg-ink-950 p-5 text-cream">
                <div className="flex items-center justify-between">
                  <span className="font-display text-3xl font-extrabold text-mustard-500">{s.month}</span>
                  <span className="text-mustard-400">{s.icon}</span>
                </div>
                <div className="mt-4 font-semibold">{s.place}</div>
                <div className="mt-1 text-sm text-ink-400">{s.note}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="mx-auto max-w-6xl px-5 py-20">
        <p className="text-sm font-bold uppercase tracking-widest text-mustard-700">How it works</p>
        <h2 className="mt-2 text-4xl font-extrabold">Four steps. One conversation.</h2>
        <div className="mt-10 grid gap-6 md:grid-cols-4">
          {STEPS.map((s) => (
            <div key={s.n} className="border-t-4 border-ink-950 pt-4">
              <span className="font-display text-sm font-extrabold text-mustard-600">{s.n}</span>
              <h3 className="mt-1 text-xl font-bold">{s.title}</h3>
              <p className="mt-1.5 text-sm text-ink-600">{s.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Security */}
      <section id="security" className="bg-ink-950 text-cream">
        <div className="mx-auto grid max-w-6xl gap-10 px-5 py-20 lg:grid-cols-2">
          <div>
            <p className="text-sm font-bold uppercase tracking-widest text-mustard-500">Security first</p>
            <h2 className="mt-2 text-4xl font-extrabold">Your money moves only when you say so.</h2>
            <p className="mt-4 text-ink-300">Every booking passes a consent gate, every payment is cryptographically verified on our servers, and your session is protected end to end.</p>
          </div>
          <ul className="grid gap-3 sm:grid-cols-2">
            {[
              [<BadgeCheck size={18} key="1" />, "Consent gate", "The AI can only propose. You approve the exact amount."],
              [<Lock size={18} key="2" />, "Verified payments", "Amount locked server-side; booked only after the money is confirmed."],
              [<Fingerprint size={18} key="3" />, "Hardened login", "Argon2 passwords, lockout and rotating sessions."],
              [<ShieldCheck size={18} key="4" />, "You're in control", "See every signed-in device and sign out anywhere."],
            ].map(([icon, title, text]) => (
              <li key={title as string} className="rounded-2xl border border-ink-700 p-5">
                <span className="text-mustard-500">{icon}</span>
                <div className="mt-2 font-semibold">{title}</div>
                <div className="mt-1 text-sm text-ink-400">{text}</div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-5 py-20 text-center">
        <SaraAvatar size={80} mood="happy" className="mx-auto" />
        <h2 className="mt-5 text-4xl font-extrabold">Where are we going?</h2>
        <p className="mt-2 text-ink-600">Create a free account and ask Sara anything about travelling in India.</p>
        <Link to={cta} className="btn-primary mt-6 px-7 py-3 text-base">Ask Sara now <ArrowRight size={18} /></Link>
      </section>

      <footer className="border-t border-ink-100">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-8 text-sm text-ink-500">
          <Logo />
          <p>Demo build · sandbox flights, trains and hotels · no real tickets are issued.</p>
        </div>
      </footer>
    </div>
  );
}
