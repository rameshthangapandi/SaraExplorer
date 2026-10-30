from datetime import datetime

from app.data.geo import AIRPORTS
from app.providers import sandbox
from app.strategist.base import Strategy, Suggestion, register


@register
class BookingTiming(Strategy):
    name = "booking_timing"
    category = "money"

    def applies_to(self, ctx):
        return ctx.travel_date is not None and ctx.origin is not None

    def suggest(self, ctx):
        days = (ctx.travel_date - ctx.today).days
        if days < 0:
            return []
        now_mult = sandbox.lead_time_multiplier(days)
        best_mult = sandbox.lead_time_multiplier(30)
        _, peak_name = sandbox.peak_for(ctx.travel_date)
        peak_note = f" Your dates fall in the {peak_name} peak, so fares are already higher than usual." if peak_name else ""
        if days > 45:
            return [Suggestion(self.name, self.category, "Wait a little before booking flights",
                               f"Domestic fares are usually lowest 3–6 weeks before travel. You are {days} days out; "
                               f"the best window opens in about {days - 45} days.{peak_note}",
                               score=55, confidence=0.7)]
        if days >= 21:
            return [Suggestion(self.name, self.category, "Book flights now — you're in the sweet spot",
                               f"You are {days} days before travel, inside the typical 3–6 week low-fare window."
                               f"{peak_note}", score=70, confidence=0.75)]
        above = int((now_mult / best_mult - 1) * 100)
        return [Suggestion(self.name, self.category, "Book flights today — prices are climbing",
                           f"Only {days} days left. Fares are already about {above}% above the 3–6 week level and "
                           f"usually keep rising as the date gets closer.{peak_note}",
                           score=85, confidence=0.8)]


@register
class DepartureTime(Strategy):
    name = "departure_time"
    category = "money"

    def applies_to(self, ctx):
        return ctx.travel_date is not None and ctx.origin is not None

    def suggest(self, ctx):
        flights = sandbox.search_flights(ctx.origin, ctx.destination["name"], ctx.travel_date, ctx.adults, ctx.today)
        if len(flights) < 2:
            return []
        cheapest, priciest = flights[0], flights[-1]
        saving = priciest["price_total"] - cheapest["price_total"]
        if saving < 500:
            return []
        dep = datetime.fromisoformat(cheapest["depart"]).strftime("%I:%M %p").lstrip("0")
        return [Suggestion(self.name, self.category, f"Take the {dep} flight",
                           f"{cheapest['airline']} {cheapest['flight_no']} at {dep} is ₹{saving:,} cheaper than the most "
                           f"expensive departure that day. Early-morning and late-night flights are usually cheapest.",
                           score=min(90, 40 + saving / 100), confidence=0.85, saving_inr=saving)]


@register
class NearbyAirport(Strategy):
    name = "nearby_airport"
    category = "money"

    def applies_to(self, ctx):
        return ctx.travel_date is not None and ctx.origin is not None and len(ctx.destination["airports"]) > 1

    def suggest(self, ctx):
        best = {}
        for code in ctx.destination["airports"]:
            flights = sandbox.search_flights(ctx.origin, code, ctx.travel_date, ctx.adults, ctx.today)
            if flights:
                best[code] = flights[0]["price_total"]
        primary = ctx.destination["airports"][0]
        if len(best) < 2 or primary not in best:
            return []
        cheapest = min(best, key=best.get)
        saving = best[primary] - best[cheapest]
        if cheapest == primary or saving < 400:
            return []
        a = AIRPORTS[cheapest]
        return [Suggestion(self.name, self.category, f"Fly into {a['name']} ({cheapest}) instead",
                           f"Cheapest fare to {cheapest} is ₹{best[cheapest]:,} vs ₹{best[primary]:,} to {primary} — "
                           f"₹{saving:,} saved. Check the transfer time from {a['city']} before switching.",
                           score=min(85, 35 + saving / 100), confidence=0.7, saving_inr=saving)]
