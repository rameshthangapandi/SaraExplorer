from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import date


@dataclass
class TripContext:
    destination: dict
    month: int
    origin: str | None = None
    travel_date: date | None = None
    nights: int = 3
    adults: int = 1
    today: date = field(default_factory=date.today)
    traveller_type: str | None = None


@dataclass
class Suggestion:
    strategy: str
    category: str          # money | time | experience | risk | comfort | corporate
    title: str
    detail: str
    score: float           # 0-100, used for ranking
    confidence: float      # 0-1
    saving_inr: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class Strategy(ABC):
    name: str
    category: str

    @abstractmethod
    def applies_to(self, ctx: TripContext) -> bool: ...

    @abstractmethod
    def suggest(self, ctx: TripContext) -> list[Suggestion]: ...


REGISTRY: list[Strategy] = []


def register(cls: type[Strategy]) -> type[Strategy]:
    REGISTRY.append(cls())
    return cls
