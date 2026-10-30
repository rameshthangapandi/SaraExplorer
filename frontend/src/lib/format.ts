export const inr = (n: number) => "₹" + Math.round(n).toLocaleString("en-IN");

export const time = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", hour12: true });

export const day = (iso: string) =>
  new Date(iso.length === 10 ? iso + "T00:00:00" : iso).toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });

export const duration = (min: number) => `${Math.floor(min / 60)}h ${String(min % 60).padStart(2, "0")}m`;

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}
