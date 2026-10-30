import { Link } from "react-router-dom";
import { cx } from "../lib/format";
import SaraAvatar from "./SaraAvatar";

export default function Logo({ dark = false, to = "/" }: { dark?: boolean; to?: string }) {
  return (
    <Link to={to} className="flex items-center gap-2.5" aria-label="Sara Explorer home">
      <SaraAvatar size={34} />
      <span className={cx("font-display text-lg font-extrabold leading-none", dark ? "text-cream" : "text-ink-950")}>
        Sara<span className="text-mustard-500">.</span>Explorer
      </span>
    </Link>
  );
}
