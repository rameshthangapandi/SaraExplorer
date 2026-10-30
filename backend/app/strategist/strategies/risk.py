from app.strategist.base import Strategy, Suggestion, register


@register
class ConnectionBuffer(Strategy):
    name = "connection_buffer"
    category = "risk"

    def applies_to(self, ctx):
        d = ctx.destination
        fog = d["region"] == "north" and ctx.month in (12, 1)
        monsoon = d["terrain"] in ("mountain", "hills", "high-altitude") and ctx.month in (6, 7, 8, 9)
        return fog or monsoon

    def suggest(self, ctx):
        d = ctx.destination
        if d["region"] == "north" and ctx.month in (12, 1):
            return [Suggestion(self.name, self.category, "Keep 6+ hours between connections (fog season)",
                               "Dense fog in North India in December–January often delays trains by hours and "
                               "disrupts early flights. Avoid tight train-to-flight connections.",
                               score=75, confidence=0.8)]
        return [Suggestion(self.name, self.category, "Add a buffer day for monsoon roads",
                           f"Landslides can block hill roads around {d['name']} during the monsoon. Keep one spare day "
                           f"before your return flight and prefer refundable bookings.", score=78, confidence=0.75)]


@register
class Permits(Strategy):
    name = "permits"
    category = "risk"

    def applies_to(self, ctx):
        return bool(ctx.destination.get("permit"))

    def suggest(self, ctx):
        return [Suggestion(self.name, self.category, "Permit needed", ctx.destination["permit"],
                           score=88, confidence=0.85)]
