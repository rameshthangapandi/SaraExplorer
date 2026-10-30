from datetime import timedelta

from app.strategist.base import Strategy, Suggestion, register

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@register
class ClosedDays(Strategy):
    name = "closed_days"
    category = "time"

    def applies_to(self, ctx):
        return ctx.travel_date is not None and bool(ctx.destination["closed"])

    def suggest(self, ctx):
        out = []
        days = [ctx.travel_date + timedelta(days=i) for i in range(max(ctx.nights, 1) + 1)]
        for place, closed_day in ctx.destination["closed"]:
            hits = [d for d in days if WEEKDAYS[d.weekday()] == closed_day]
            if not hits:
                continue
            open_days = [d for d in days if WEEKDAYS[d.weekday()] != closed_day]
            alt = f" Plan it for {open_days[0].strftime('%a %d %b')} instead." if open_days else \
                " Your whole stay is on that day — consider shifting dates."
            out.append(Suggestion(self.name, self.category, f"{place} is closed on {closed_day}s",
                                  f"{place} is closed on {hits[0].strftime('%a %d %b')}.{alt}",
                                  score=80, confidence=0.9))
        return out
