from app.planner.groups import profile
from app.strategist.base import Strategy, Suggestion, register

TIPS = {
    "couple": [("Plan for two", "Look for lake-view, mountain-view or spa stays and keep one evening free for a sunset spot; "
                "avoid red-eye flights so the trip starts relaxed.")],
    "family": [("Plan around the children", "Keep travel days under about 10 hours, book family rooms with breakfast, "
                "and avoid departures before 6 AM or after 10 PM.")],
    "friends": [("Plan for the group", "Split cabs and SUVs to cut per-person cost, look at weekend events and nightlife, "
                 "and prefer hotels with free cancellation in case plans change.")],
    "seniors": [("Plan for comfort", "Ask for lower berths under the senior-citizen quota, choose hotels with a lift and "
                 "airport pickup, and keep sightseeing to the mornings.")],
    "solo": [("Plan solo", "Metro and bike taxis are the cheapest way around cities; hostels and guesthouses with good "
              "reviews suit solo travellers.")],
    "business": [("Plan for work", "Prefer morning flights, hotels with reliable Wi-Fi and airport pickup, and keep a "
                  "buffer before meetings.")],
}


@register
class GroupFit(Strategy):
    name = "group_fit"
    category = "comfort"

    def applies_to(self, ctx):
        return bool(profile(ctx.traveller_type))

    def suggest(self, ctx):
        g = profile(ctx.traveller_type)
        out = [Suggestion(self.name, self.category, t, d, score=72, confidence=0.8) for t, d in TIPS.get(ctx.traveller_type, [])]
        if ctx.destination.get("terrain") in g["avoid_terrain"]:
            out.append(Suggestion(self.name, "risk", f"{ctx.destination['name']} may be hard for {g['label'].lower()}",
                                  "This is a high-altitude destination: thin air and long road journeys are tiring for young "
                                  "children and older travellers. Consider a lower destination or extra rest days.",
                                  score=92, confidence=0.85))
        elif sum(1 for t in g["dest_tags"] if t in ctx.destination["tags"]) >= 1:
            out.append(Suggestion(self.name, self.category, f"{ctx.destination['name']} suits {g['label'].lower()}",
                                  f"It matches what {g['label'].lower()} usually look for: "
                                  f"{', '.join(t for t in g['dest_tags'] if t in ctx.destination['tags'])}.", score=60, confidence=0.7))
        return out
