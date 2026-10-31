from app.data.destinations import MONTHS
from app.strategist.base import Strategy, Suggestion, register

LABEL = {1: "a poor time", 2: "not ideal", 3: "a fair time", 4: "a good time", 5: "an excellent time"}


@register
class Weather(Strategy):
    name = "weather"
    category = "experience"

    def applies_to(self, ctx):
        return True

    def suggest(self, ctx):
        d = ctx.destination
        r = d["ratings"][ctx.month - 1]
        best = [MONTHS[i] for i, v in enumerate(d["ratings"]) if v == 5]
        best_txt = f" Best months: {', '.join(best)}." if best else ""
        if r >= 4:
            return [Suggestion(self.name, self.category, f"{MONTHS[ctx.month - 1]} is {LABEL[r]} for {d['name']}",
                               f"Weather is usually pleasant then.{best_txt}", score=40 + r * 5, confidence=0.75)]
        return [Suggestion(self.name, self.category, f"{MONTHS[ctx.month - 1]} is {LABEL[r]} for {d['name']}",
                           f"{(d['tips'][0].rstrip('.') + '.') if d['tips'] else 'Weather is often unfavourable then.'}{best_txt}",
                           score=95 - r * 10, confidence=0.75)]


@register
class ShoulderSeason(Strategy):
    name = "shoulder_season"
    category = "experience"

    def applies_to(self, ctx):
        return ctx.month in ctx.destination["peak"] or ctx.destination["ratings"][ctx.month - 1] <= 3

    def suggest(self, ctx):
        d = ctx.destination
        for offset in (1, -1, 2, -2):
            m = (ctx.month - 1 + offset) % 12 + 1
            if d["ratings"][m - 1] >= 4 and m not in d["peak"]:
                why = "fewer crowds and lower hotel prices" if ctx.month in d["peak"] else "much better weather"
                return [Suggestion(self.name, self.category, f"Consider {MONTHS[m - 1]} instead",
                                   f"{MONTHS[m - 1]} is still a good time for {d['name']} with {why}.",
                                   score=65, confidence=0.65)]
        return []


@register
class Festivals(Strategy):
    name = "festivals"
    category = "experience"

    def applies_to(self, ctx):
        return any(ctx.month in months for _, months, _ in ctx.destination["festivals"])

    def suggest(self, ctx):
        out = []
        for fname, months, note in ctx.destination["festivals"]:
            if ctx.month in months:
                out.append(Suggestion(self.name, self.category, f"{fname} happens around your trip",
                                      f"{note}. Dates vary by year — book stays early if you want to attend, "
                                      f"or avoid these days if you prefer quiet.", score=60, confidence=0.6))
        return out
