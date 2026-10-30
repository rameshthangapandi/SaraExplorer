import { cx } from "../lib/format";

export type SaraMood = "idle" | "thinking" | "happy" | "alert" | "listening";

/** Sara, the Sara Explorer mascot: a friendly traveller with a mustard face and a black bob. */
export default function SaraAvatar({ size = 40, mood = "idle", className }: { size?: number; mood?: SaraMood; className?: string }) {
  const eyesY = mood === "thinking" ? 33 : 35;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label={`Sara (${mood})`}
      className={cx("shrink-0", mood === "thinking" && "animate-pulse", className)}
    >
      <circle cx="32" cy="32" r="32" fill="#0b0b0b" />
      <circle cx="32" cy="35" r="19" fill="#e3a812" />
      {/* hair */}
      <path d="M12.5 33c0-13 8.6-21 19.5-21s19.5 8 19.5 21c-3-6-9-9.5-14.5-10-2 3.5-7 5.5-13 5.5-4.4 0-8.6 1.6-11.5 4.5z" fill="#0b0b0b" />
      {/* travel pin in hair */}
      <circle cx="44" cy="20" r="3" fill="#fbf8f0" />
      <circle cx="44" cy="20" r="1.2" fill="#e3a812" />
      {/* eyes */}
      <g className="animate-blink" style={{ transformOrigin: `32px ${eyesY}px` }}>
        {mood === "happy" ? (
          <>
            <path d="M23 36q2.5-3 5 0" stroke="#0b0b0b" strokeWidth="2.4" fill="none" strokeLinecap="round" />
            <path d="M36 36q2.5-3 5 0" stroke="#0b0b0b" strokeWidth="2.4" fill="none" strokeLinecap="round" />
          </>
        ) : (
          <>
            <circle cx="25.5" cy={eyesY} r="2.3" fill="#0b0b0b" />
            <circle cx="38.5" cy={eyesY} r="2.3" fill="#0b0b0b" />
          </>
        )}
      </g>
      {/* mouth */}
      {mood === "alert" ? (
        <circle cx="32" cy="44" r="2.4" fill="#0b0b0b" />
      ) : mood === "listening" ? (
        <ellipse cx="32" cy="44" rx="3.2" ry="2.4" fill="#0b0b0b" />
      ) : (
        <path
          d={mood === "happy" ? "M25 42c3.8 4.5 10.2 4.5 14 0" : "M26.5 42.5c3 2.6 8 2.6 11 0"}
          stroke="#0b0b0b"
          strokeWidth="2.4"
          fill="none"
          strokeLinecap="round"
        />
      )}
      {/* cheeks */}
      <circle cx="21" cy="41" r="2.2" fill="#c2870b" opacity="0.45" />
      <circle cx="43" cy="41" r="2.2" fill="#c2870b" opacity="0.45" />
    </svg>
  );
}
