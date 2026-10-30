import { Eye, EyeOff, Loader2, Lock, ShieldCheck } from "lucide-react";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import Logo from "../components/Logo";
import SaraAvatar from "../components/SaraAvatar";
import { useAuth } from "../lib/auth";
import { cx } from "../lib/format";

function Layout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <aside className="relative hidden overflow-hidden bg-ink-950 p-10 text-cream lg:flex lg:flex-col lg:justify-between">
        <div className="bg-grid absolute inset-0" aria-hidden />
        <div className="relative"><Logo dark /></div>
        <div className="relative">
          <SaraAvatar size={88} mood="happy" className="animate-float" />
          <blockquote className="mt-6 font-display text-3xl font-bold leading-snug">
            "Tell me where your heart wants to go. I'll handle the trains, the timing and the fine print."
          </blockquote>
          <p className="mt-3 text-mustard-400">— Sara, your travel guide</p>
        </div>
        <div className="relative flex items-center gap-2 text-sm text-ink-400"><ShieldCheck size={16} className="text-mustard-500" /> Protected sign-in · encrypted sessions</div>
      </aside>
      <main className="flex items-center justify-center px-5 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden"><Logo /></div>
          <h1 className="text-3xl font-extrabold">{title}</h1>
          <p className="mt-1.5 text-sm text-ink-500">{subtitle}</p>
          <div className="mt-8">{children}</div>
        </div>
      </main>
    </div>
  );
}

function PasswordInput({ value, onChange, autoComplete, id }: { value: string; onChange: (v: string) => void; autoComplete: string; id: string }) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input id={id} className="input pr-11" type={show ? "text" : "password"} value={value} onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete} required maxLength={128} />
      <button type="button" onClick={() => setShow(!show)} className="absolute inset-y-0 right-0 px-3 text-ink-400 hover:text-ink-900"
        aria-label={show ? "Hide password" : "Show password"}>
        {show ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  );
}

function Remember({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-start gap-2.5 text-sm text-ink-600">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-0.5 size-4 accent-ink-950" />
      <span>Keep me signed in for 7 days <span className="block text-xs text-ink-400">Unchecked: you stay signed in until you close the browser.</span></span>
    </label>
  );
}

export function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const next = (loc.state as { from?: string } | null)?.from ?? "/app";

  if (user) return <Navigate to={next} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password, remember);
      nav(next, { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Layout title="Welcome back" subtitle="Log in to continue planning with Sara.">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
        </div>
        <div>
          <label className="label" htmlFor="password">Password</label>
          <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="current-password" />
        </div>
        <Remember checked={remember} onChange={setRemember} />
        {error && <p role="alert" className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
        <button className="btn-dark w-full py-3" disabled={busy}>
          {busy ? <Loader2 size={18} className="animate-spin" /> : <Lock size={16} />} Log in
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-ink-500">
        New to Sara Explorer? <Link to="/register" className="font-semibold text-ink-950 underline decoration-mustard-500 decoration-2 underline-offset-4">Create an account</Link>
      </p>
    </Layout>
  );
}

const RULES: [string, (p: string) => boolean][] = [
  ["10+ characters", (p) => p.length >= 10],
  ["Upper & lower case", (p) => /[a-z]/.test(p) && /[A-Z]/.test(p)],
  ["A number", (p) => /\d/.test(p)],
  ["A symbol", (p) => /[^A-Za-z0-9]/.test(p)],
];

export function Register() {
  const { user, register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", phone: "", password: "", confirm: "" });
  const [remember, setRemember] = useState(true);
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const passed = useMemo(() => RULES.map(([, test]) => test(form.password)), [form.password]);
  const strong = passed.every(Boolean);

  if (user) return <Navigate to="/app" replace />;

  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!strong) return setError("Please choose a stronger password.");
    if (form.password !== form.confirm) return setError("Passwords don't match.");
    setBusy(true);
    setError("");
    try {
      await register({ name: form.name, email: form.email, phone: form.phone.trim() || undefined, password: form.password, remember });
      nav("/app", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Layout title="Create your account" subtitle="Free forever for travellers. Takes 30 seconds.">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label" htmlFor="name">Full name</label>
          <input id="name" className="input" value={form.name} onChange={set("name")} autoComplete="name" required minLength={2} maxLength={100} />
        </div>
        <div>
          <label className="label" htmlFor="remail">Email</label>
          <input id="remail" className="input" type="email" value={form.email} onChange={set("email")} autoComplete="email" required />
        </div>
        <div>
          <label className="label" htmlFor="phone">Mobile <span className="normal-case text-ink-400">(optional)</span></label>
          <input id="phone" className="input" type="tel" value={form.phone} onChange={set("phone")} autoComplete="tel" placeholder="+91 98765 43210" pattern="\+?[0-9 ]{10,15}" />
        </div>
        <div>
          <label className="label" htmlFor="rpassword">Password</label>
          <PasswordInput id="rpassword" value={form.password} onChange={(v) => setForm({ ...form, password: v })} autoComplete="new-password" />
          <div className="mt-2 grid grid-cols-2 gap-1">
            {RULES.map(([label], i) => (
              <span key={label} className={cx("flex items-center gap-1.5 text-xs", passed[i] ? "text-emerald-700" : "text-ink-400")}>
                <span className={cx("size-1.5 rounded-full", passed[i] ? "bg-emerald-600" : "bg-ink-300")} /> {label}
              </span>
            ))}
          </div>
        </div>
        <div>
          <label className="label" htmlFor="confirm">Confirm password</label>
          <PasswordInput id="confirm" value={form.confirm} onChange={(v) => setForm({ ...form, confirm: v })} autoComplete="new-password" />
        </div>
        <Remember checked={remember} onChange={setRemember} />
        <label className="flex cursor-pointer items-start gap-2.5 text-sm text-ink-600">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-0.5 size-4 accent-ink-950" required />
          <span>I agree that Sara Explorer stores my trip data to plan and book my trips.</span>
        </label>
        {error && <p role="alert" className="rounded-lg bg-red-50 p-2.5 text-sm text-red-700">{error}</p>}
        <button className="btn-primary w-full py-3" disabled={busy || !agree}>
          {busy && <Loader2 size={18} className="animate-spin" />} Create account
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-ink-500">
        Already have an account? <Link to="/login" className="font-semibold text-ink-950 underline decoration-mustard-500 decoration-2 underline-offset-4">Log in</Link>
      </p>
    </Layout>
  );
}
