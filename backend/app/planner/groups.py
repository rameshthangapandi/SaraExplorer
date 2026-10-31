"""Traveller groups: how a honeymoon couple, a family with children, a group of friends, senior citizens,
a solo traveller or a business traveller change what Sara recommends.

Profiles only change *preferences* (ranking and scoring). Hard constraints such as the budget are never relaxed."""

GROUPS: dict[str, dict] = {
    "solo": {
        "label": "Solo traveller",
        "dest_tags": {"backpacking": 3, "offbeat": 2, "culture": 2, "adventure": 2, "heritage": 1, "yoga": 1},
        "avoid_terrain": [],
        "hotel_amenities": {"Free Wi-Fi": 2, "Free cancellation": 1},
        "preferred_stars": 3,
        "min_train_class": "SL", "avoid_early": False, "avoid_late": False, "prefer_flight": False,
        "max_comfortable_hours": 24,
        "ride_modes": {"bike": -60, "metro": -40, "bus": -20, "suv": 120},
    },
    "couple": {
        "label": "Couple / honeymoon",
        "dest_tags": {"honeymoon": 4, "beach": 2, "lakes": 2, "hills": 2, "relax": 2, "palaces": 1},
        "avoid_terrain": [],
        "hotel_amenities": {"Spa": 3, "Lake view": 3, "Mountain view": 3, "Pool": 2, "Breakfast included": 1},
        "preferred_stars": 5,
        "min_train_class": "3A", "avoid_early": True, "avoid_late": False, "prefer_flight": True,
        "max_comfortable_hours": 12,
        "ride_modes": {"cab": -150, "sedan": -120, "bus": 150, "bike": 200, "metro": 100, "auto": 40},
    },
    "family": {
        "label": "Family with children",
        "dest_tags": {"family": 4, "beach": 2, "backwaters": 2, "nature": 2, "heritage": 1, "hills": 1},
        "avoid_terrain": ["high-altitude"],
        "hotel_amenities": {"Family rooms": 4, "Breakfast included": 2, "Pool": 2, "Lift": 1, "Parking": 1},
        "preferred_stars": 4,
        "min_train_class": "3A", "avoid_early": True, "avoid_late": True, "prefer_flight": False,
        "max_comfortable_hours": 10,
        "ride_modes": {"cab": -60, "suv": -40, "bike": 400, "auto": 60, "bus": 100},
    },
    "friends": {
        "label": "Friends group",
        "dest_tags": {"nightlife": 4, "adventure": 3, "beach": 2, "food": 2, "roadtrip": 2, "snow": 1},
        "avoid_terrain": [],
        "hotel_amenities": {"Pool": 2, "Free Wi-Fi": 1, "Free cancellation": 1},
        "preferred_stars": 3,
        "min_train_class": "SL", "avoid_early": False, "avoid_late": False, "prefer_flight": False,
        "max_comfortable_hours": 20,
        "ride_modes": {"suv": -40, "cab": -30, "bike": 40},
    },
    "seniors": {
        "label": "Senior citizens",
        "dest_tags": {"spiritual": 4, "heritage": 3, "relax": 2, "backwaters": 2, "family": 1},
        "avoid_terrain": ["high-altitude"],
        "hotel_amenities": {"Lift": 4, "Airport pickup": 3, "Pure-veg restaurant": 2, "Breakfast included": 1},
        "preferred_stars": 4,
        "min_train_class": "3A", "avoid_early": True, "avoid_late": True, "prefer_flight": True,
        "max_comfortable_hours": 8,
        "ride_modes": {"cab": -80, "suv": -40, "bike": 500, "auto": 80, "bus": 150, "metro": 60},
    },
    "business": {
        "label": "Business traveller",
        "dest_tags": {"city": 4, "food": 1},
        "avoid_terrain": [],
        "hotel_amenities": {"Free Wi-Fi": 4, "Airport pickup": 2, "Breakfast included": 1},
        "preferred_stars": 4,
        "min_train_class": "2A", "avoid_early": False, "avoid_late": False, "prefer_flight": True,
        "max_comfortable_hours": 6,
        "ride_modes": {"cab": -60, "bus": 150, "bike": 80},
    },
}

TRAIN_RANK = {"SL": 0, "CC": 1, "3A": 1, "2A": 2, "1A": 3}


def profile(kind: str | None) -> dict | None:
    return GROUPS.get(kind or "")


def destination_fit(dest: dict, kind: str | None) -> float:
    """Extra score for how well a destination suits the group (negative if unsuitable)."""
    g = profile(kind)
    if not g:
        return 0.0
    if dest.get("terrain") in g["avoid_terrain"]:
        return -6.0
    return float(sum(w for tag, w in g["dest_tags"].items() if tag in dest["tags"] or tag == dest.get("terrain")))


def hotel_bonus(hotel: dict, kind: str | None) -> tuple[int, list[str]]:
    """Rupee-equivalent preference bonus for a stay, and the matching features (for explanations)."""
    g = profile(kind)
    if not g:
        return 0, []
    matched = [a for a in hotel["amenities"] if a in g["hotel_amenities"]]
    bonus = sum(g["hotel_amenities"][a] for a in matched) * 1200
    bonus -= abs(hotel["stars"] - g["preferred_stars"]) * 900
    return bonus, matched


def transport_penalty(option: dict, kind: str | None) -> tuple[int, list[str]]:
    """Rupee-equivalent penalty for legs that do not suit the group, with reasons."""
    g = profile(kind)
    if not g:
        return 0, []
    pen, why = 0, []
    hour = int(option["depart"][11:13])
    arr_hour = int(option["arrive"][11:13])
    if g["avoid_early"] and hour < 6:
        pen += 3000
        why.append("very early departure")
    if g["avoid_late"] and (hour >= 22 or arr_hour < 5):
        pen += 2500
        why.append("late-night travel")
    if "class" in option and TRAIN_RANK.get(option["class"], 1) < TRAIN_RANK[g["min_train_class"]]:
        pen += 4000
        why.append(f"{option['class']} class below {g['min_train_class']}")
    if g["prefer_flight"] and "train_no" in option:
        pen += 1500
    hours = option["duration_min"] / 60
    if hours > g["max_comfortable_hours"]:
        pen += int((hours - g["max_comfortable_hours"]) * 400)
        why.append(f"{hours:.0f}-hour journey")
    return pen, why
