import { ArrowUp, Loader2, Mic, PanelLeft, Plus, Square, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import CardRenderer from "../components/cards/Cards";
import SaraAvatar, { type SaraMood } from "../components/SaraAvatar";
import { api, streamChat, uploadAudio, type Card } from "../lib/api";
import { useAuth } from "../lib/auth";
import { cx } from "../lib/format";

type Msg = { id: string; role: "user" | "assistant"; content: string; cards: Card[]; status?: string; error?: boolean };
type Conv = { id: string; title: string };

const SUGGESTIONS = [
  "Plan 4 days in Goa in February for 2, budget ₹40k",
  "Where should I go in July?",
  "Do I need a permit for Tawang?",
  "Cheapest way from Delhi to Jaipur next Friday",
  "Best time to visit Ladakh?",
  "Find trains from Mumbai to Goa for next Saturday",
];

const uid = () => Math.random().toString(36).slice(2);

function useRecorder(onText: (t: string) => void) {
  const [state, setState] = useState<"idle" | "recording" | "transcribing">("idle");
  const [error, setError] = useState("");
  const rec = useRef<MediaRecorder | null>(null);

  const start = async () => {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = ["audio/webm", "audio/mp4", "audio/ogg"].find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
      const r = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      const chunks: Blob[] = [];
      r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      r.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setState("transcribing");
        try {
          const { text } = await uploadAudio(new Blob(chunks, { type: r.mimeType || "audio/webm" }));
          if (text) onText(text);
          else setError("I didn't catch that — try again?");
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setState("idle");
        }
      };
      r.start();
      rec.current = r;
      setState("recording");
      setTimeout(() => r.state === "recording" && r.stop(), 60_000);
    } catch {
      setError("Microphone access was blocked.");
    }
  };
  const stop = () => rec.current?.state === "recording" && rec.current.stop();
  return { state, error, start, stop };
}

export default function AskSara() {
  const { user } = useAuth();
  const [convs, setConvs] = useState<Conv[]>([]);
  const [convId, setConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const abort = useRef<AbortController | null>(null);

  const loadConvs = useCallback(() => api<Conv[]>("/api/chat/conversations").then(setConvs).catch(() => undefined), []);
  useEffect(() => {
    loadConvs();
  }, [loadConvs]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const recorder = useRecorder((t) => {
    setInput((prev) => (prev ? prev + " " : "") + t);
    textarea.current?.focus();
  });

  const openConv = async (id: string) => {
    abort.current?.abort();
    setShowHistory(false);
    const data = await api<{ id: string; messages: Msg[] }>(`/api/chat/conversations/${id}`);
    setConvId(id);
    setMessages(data.messages.map((m) => ({ ...m, cards: m.cards ?? [] })));
  };

  const newChat = () => {
    abort.current?.abort();
    setConvId(null);
    setMessages([]);
    setShowHistory(false);
    textarea.current?.focus();
  };

  const removeConv = async (id: string) => {
    await api(`/api/chat/conversations/${id}`, { method: "DELETE" });
    if (id === convId) newChat();
    loadConvs();
  };

  const send = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message || busy) return;
      setInput("");
      setBusy(true);
      const replyId = uid();
      setMessages((m) => [...m, { id: uid(), role: "user", content: message, cards: [] },
        { id: replyId, role: "assistant", content: "", cards: [], status: "Thinking…" }]);
      const patch = (fn: (m: Msg) => Msg) => setMessages((all) => all.map((m) => (m.id === replyId ? fn(m) : m)));
      const ctrl = new AbortController();
      abort.current = ctrl;
      try {
        await streamChat({ message, conversation_id: convId }, (ev) => {
          switch (ev.type) {
            case "conversation": setConvId(ev.conversation_id); break;
            case "token": patch((m) => ({ ...m, content: m.content + ev.text, status: undefined })); break;
            case "step": patch((m) => (m.content ? { ...m, content: m.content + "\n\n" } : m)); break;
            case "status": patch((m) => ({ ...m, status: ev.text })); break;
            case "card": patch((m) => ({ ...m, cards: [...m.cards, ev.card] })); break;
            case "replace": patch((m) => ({ ...m, content: ev.text })); break;
            case "error": patch((m) => ({ ...m, content: (m.content ? m.content + "\n\n" : "") + ev.text, error: true })); break;
            case "done": patch((m) => ({ ...m, status: undefined })); break;
          }
        }, ctrl.signal);
      } catch (e) {
        if (!ctrl.signal.aborted) patch((m) => ({ ...m, content: (e as Error).message, error: true, status: undefined }));
      } finally {
        patch((m) => ({ ...m, status: undefined }));
        setBusy(false);
        loadConvs();
      }
    },
    [busy, convId, loadConvs],
  );

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const mood: SaraMood = recorder.state === "recording" ? "listening" : busy ? "thinking" : "idle";
  const firstName = user?.name.split(" ")[0] ?? "there";

  return (
    <div className="flex h-full">
      {/* Conversation history */}
      <aside className={cx("w-64 shrink-0 flex-col border-r border-ink-100 bg-white", showHistory ? "fixed inset-y-0 left-0 z-30 flex shadow-2xl" : "hidden xl:flex")}>
        <div className="p-3">
          <button onClick={newChat} className="btn-dark w-full"><Plus size={16} /> New chat</button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-3">
          <div className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-400">Recent</div>
          {convs.length === 0 && <p className="px-2 text-xs text-ink-400">No chats yet.</p>}
          {convs.map((c) => (
            <div key={c.id} className={cx("group flex items-center rounded-lg", c.id === convId ? "bg-mustard-100" : "hover:bg-ink-100")}>
              <button onClick={() => openConv(c.id)} className="flex-1 truncate px-2 py-2 text-left text-sm">{c.title}</button>
              <button onClick={() => removeConv(c.id)} className="p-2 text-ink-300 opacity-0 hover:text-red-600 group-hover:opacity-100" aria-label={`Delete chat ${c.title}`}>
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </aside>
      {showHistory && <div className="fixed inset-0 z-20 bg-ink-950/30 xl:hidden" onClick={() => setShowHistory(false)} />}

      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-3 border-b border-ink-100 bg-white/70 px-4 py-2.5 backdrop-blur">
          <button onClick={() => setShowHistory(true)} className="rounded-lg p-1.5 text-ink-500 hover:bg-ink-100 xl:hidden" aria-label="Show chat history"><PanelLeft size={18} /></button>
          <SaraAvatar size={32} mood={mood} />
          <div>
            <div className="text-sm font-bold leading-tight">Ask Sara</div>
            <div className="text-[11px] text-ink-500">{busy ? "Working on it…" : "Your India travel guide"}</div>
          </div>
          <button onClick={newChat} className="btn-ghost ml-auto px-3 py-1.5 text-xs"><Plus size={14} /> New</button>
        </div>

        <div ref={scroller} className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-6">
            {messages.length === 0 ? (
              <div className="pt-10 text-center sm:pt-14">
                <SaraAvatar size={84} mood="happy" className="mx-auto animate-float" />
                <h1 className="mt-5 text-3xl font-extrabold sm:text-4xl">Namaste, {firstName}! Where to?</h1>
                <p className="mx-auto mt-2 max-w-md text-ink-500">Plan a trip, ask about the best time to go, check permits, or have me find and hold bookings for your approval.</p>
                <div className="mx-auto mt-8 grid max-w-2xl gap-2 sm:grid-cols-2">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} onClick={() => send(s)} className="card px-4 py-3 text-left text-sm font-medium transition hover:-translate-y-0.5 hover:border-ink-900">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {messages.map((m) =>
                  m.role === "user" ? (
                    <div key={m.id} className="flex justify-end">
                      <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-ink-950 px-4 py-2.5 text-[15px] text-cream">{m.content}</div>
                    </div>
                  ) : (
                    <div key={m.id} className="flex gap-3">
                      <SaraAvatar size={32} mood={m.status ? "thinking" : m.error ? "alert" : "idle"} className="mt-0.5" />
                      <div className="min-w-0 flex-1 space-y-3">
                        {m.content && (
                          <div className={cx("prose-sara", m.error && "text-red-700")}>
                            <Markdown remarkPlugins={[remarkGfm]} components={{ a: (p) => <a {...p} target="_blank" rel="noopener noreferrer" /> }}>
                              {m.content}
                            </Markdown>
                          </div>
                        )}
                        {m.cards.map((c, i) => <CardRenderer key={i} card={c} onSend={send} />)}
                        {m.status && (
                          <div className="flex items-center gap-2 text-sm text-ink-500">
                            <Loader2 size={14} className="animate-spin text-mustard-600" /> {m.status}
                          </div>
                        )}
                      </div>
                    </div>
                  ),
                )}
              </div>
            )}
          </div>
        </div>

        {/* Composer */}
        <div className="border-t border-ink-100 bg-cream px-4 pb-4 pt-3">
          <div className="mx-auto max-w-3xl">
            {recorder.error && <p className="mb-2 text-xs text-red-600">{recorder.error}</p>}
            <div className="flex items-end gap-2 rounded-3xl border border-ink-200 bg-white p-2 shadow-sm focus-within:border-ink-900 focus-within:ring-4 focus-within:ring-mustard-200">
              <button
                onClick={recorder.state === "recording" ? recorder.stop : recorder.start}
                disabled={recorder.state === "transcribing" || busy}
                className={cx("grid size-10 shrink-0 place-items-center rounded-full transition",
                  recorder.state === "recording" ? "animate-pulse bg-red-600 text-white" : "bg-ink-100 text-ink-700 hover:bg-mustard-200")}
                aria-label={recorder.state === "recording" ? "Stop recording" : "Speak to Sara"}
                title={recorder.state === "recording" ? "Stop recording" : "Speak to Sara"}
              >
                {recorder.state === "transcribing" ? <Loader2 size={18} className="animate-spin" /> : recorder.state === "recording" ? <Square size={16} /> : <Mic size={18} />}
              </button>
              <textarea
                ref={textarea}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKey}
                rows={1}
                maxLength={4000}
                placeholder={recorder.state === "recording" ? "Listening… tap stop when done" : "Ask Sara anything about travelling in India…"}
                className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2.5 text-[15px] outline-none placeholder:text-ink-400"
                style={{ fieldSizing: "content" } as CSSProperties}
              />
              <button onClick={() => send(input)} disabled={!input.trim() || busy}
                className="grid size-10 shrink-0 place-items-center rounded-full bg-mustard-500 text-ink-950 transition hover:bg-mustard-400 disabled:bg-ink-100 disabled:text-ink-300"
                aria-label="Send">
                {busy ? <Loader2 size={18} className="animate-spin" /> : <ArrowUp size={18} />}
              </button>
            </div>
            <p className="mt-2 text-center text-[11px] text-ink-400">Sara never books without your approval and a confirmed payment.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
