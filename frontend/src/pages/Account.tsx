import { Laptop, Loader2, LogOut, ShieldCheck } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { api, type User } from "../lib/api";
import { useAuth } from "../lib/auth";
import { day, inr } from "../lib/format";
import { PageHeader } from "./Strategist";

type Session = { id: string; user_agent: string; ip: string; created_at: string; expires_at: string; remember: boolean; current: boolean };

function device(ua: string) {
  const browser = /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox" : /Safari\//.test(ua) ? "Safari" : "Browser";
  const os = /Windows/.test(ua) ? "Windows" : /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iOS" : /Mac OS/.test(ua) ? "macOS" : /Linux/.test(ua) ? "Linux" : "device";
  return `${browser} on ${os}`;
}

export default function Account() {
  const { user, setUser, logoutAll } = useAuth();
  const [form, setForm] = useState({ name: user?.name ?? "", phone: user?.phone ?? "", spend_cap_inr: user?.spend_cap_inr ?? 200000 });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [confirmAll, setConfirmAll] = useState(false);

  const loadSessions = () => api<Session[]>("/api/auth/sessions").then(setSessions).catch(() => undefined);
  useEffect(() => {
    loadSessions();
  }, []);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMsg("");
    try {
      const u = await api<User>("/api/account/settings", {
        method: "PATCH",
        body: { name: form.name, phone: form.phone.trim() || null, spend_cap_inr: form.spend_cap_inr },
      });
      setUser(u);
      setMsg("Saved.");
    } catch (err) {
      setMsg((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const revoke = async (id: string) => {
    await api(`/api/auth/sessions/${id}`, { method: "DELETE" });
    loadSessions();
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <PageHeader title="Account & Security" text="Your profile, booking limits and every device signed in to your account." />

      <div className="grid gap-6 lg:grid-cols-2">
        <form onSubmit={save} className="card space-y-4 p-5">
          <h2 className="text-lg font-bold">Profile & limits</h2>
          <div>
            <label className="label" htmlFor="a-name">Name</label>
            <input id="a-name" className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} minLength={2} maxLength={100} required />
          </div>
          <div>
            <label className="label" htmlFor="a-email">Email</label>
            <input id="a-email" className="input bg-ink-100" value={user?.email ?? ""} disabled />
          </div>
          <div>
            <label className="label" htmlFor="a-phone">Mobile</label>
            <input id="a-phone" className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} pattern="\+?[0-9 ]{10,15}" placeholder="+91 98765 43210" />
          </div>
          <div>
            <label className="label" htmlFor="a-cap">Spending limit per booking</label>
            <input id="a-cap" type="number" min={1000} max={500000} step={1000} className="input" value={form.spend_cap_inr}
              onChange={(e) => setForm({ ...form, spend_cap_inr: +e.target.value })} />
            <p className="mt-1 text-xs text-ink-500">Sara can't propose bookings above {inr(form.spend_cap_inr)}. Maximum ₹5,00,000.</p>
          </div>
          <div className="flex items-center gap-3">
            <button className="btn-dark" disabled={saving}>{saving && <Loader2 size={16} className="animate-spin" />} Save changes</button>
            {msg && <span className="text-sm text-ink-600">{msg}</span>}
          </div>
        </form>

        <div className="card p-5">
          <h2 className="flex items-center gap-2 text-lg font-bold"><ShieldCheck size={18} className="text-mustard-600" /> Signed-in devices</h2>
          <div className="mt-4 space-y-2">
            {sessions.map((s) => (
              <div key={s.id} className="flex items-center gap-3 rounded-xl border border-ink-100 p-3">
                <Laptop size={18} className="text-ink-400" />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold">{device(s.user_agent)} {s.current && <span className="ml-1 rounded-full bg-mustard-200 px-2 py-0.5 text-[10px] font-bold uppercase">This device</span>}</div>
                  <div className="text-xs text-ink-500">{s.ip} · since {day(s.created_at)} · {s.remember ? `until ${day(s.expires_at)}` : "until browser closes"}</div>
                </div>
                {!s.current && <button onClick={() => revoke(s.id)} className="btn-ghost px-3 py-1.5 text-xs">Sign out</button>}
              </div>
            ))}
          </div>
          <div className="mt-5 border-t border-ink-100 pt-4">
            {confirmAll ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-ink-600">Sign out of every device, including this one?</span>
                <button className="btn-ghost px-3 py-1.5" onClick={() => setConfirmAll(false)}>No</button>
                <button className="btn-dark px-3 py-1.5" onClick={logoutAll}>Yes, sign out everywhere</button>
              </div>
            ) : (
              <button className="btn-outline" onClick={() => setConfirmAll(true)}><LogOut size={16} /> Sign out everywhere</button>
            )}
          </div>
          <ul className="mt-5 space-y-1.5 text-xs text-ink-500">
            <li>• Sara never asks for your password, OTP or UPI PIN in chat.</li>
            <li>• After 5 wrong passwords the account is locked for 15 minutes.</li>
            <li>• Every approval and payment is recorded in a security audit log.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
