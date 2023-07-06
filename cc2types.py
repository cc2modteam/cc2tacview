"""Type relationships with tacview and cc2"""
import dataclasses
from typing import Optional, List, Dict, Any
from cc2utils import m2deg


@dataclasses.dataclass
class CC2Item:
    shortname: str
    name_prefix: str
    tags: List[str] = dataclasses.field(default_factory=list)

    def is_ship(self) -> bool:
        return "Watercraft" in self.tags

    def is_air(self) -> bool:
        return "Air" in self.tags

    def is_ground(self) -> bool:
        return not self.is_air() and not self.is_ship()


typemap = {
    0: CC2Item("CRR",
                 "TARAWA",
                 tags=["Heavy", "Sea", "Watercraft", "AircraftCarrier"]),
    8: CC2Item("ALB",
                 "MQ-9",
                 tags=["Light", "Air", "FixedWing"]),
    10: CC2Item("MNT",
                  "",
                  tags=["Medium", "Air", "FixedWing"]),
    12: CC2Item("RZR",
                  "",
                  tags=["Light", "Air", "Rotorcraft"]),
    14: CC2Item("PTR",
                  "V22",
                  tags=["Medium", "Air", "Rotorcraft"]),
}


@dataclasses.dataclass
class Unit:
    uid: str = "x"
    typ: str = "-1"
    x: Optional[float] = None
    y: Optional[float] = None
    alt: Optional[float] = None
    team: int = -1
    last_printed: int = -1
    docked: bool = True
    event_takeoff: Optional[bool] = None
    event_landed: Optional[bool] = None
    ttl: int = 2

    def map_id(self) -> str:
        return self.uid[1:]

    def update(self, data: dict):
        for prop in ["x", "y", "alt"]:
            value = data.get(prop, None)
            if value is not None:
                setattr(self, prop, float(value))
        team = data.get("team", None)
        if team is not None:
            self.team = int(team)
        if "docked" in data:
            docked_now = self.docked
            self.docked = data.get("docked") == "true"
            if docked_now != self.docked:
                if self.docked:

                    # landed
                    self.event_landed = True
                    self.event_takeoff = None
                else:
                    self.event_landed = None
                    self.event_takeoff = True

    @property
    def definition_index(self) -> int:
        return int(self.typ)

    def get_events(self) -> List[str]:
        events = []
        if self.event_landed:
            events.append("Landed")
        elif self.event_takeoff:
            events.append("TakenOff")
        return events

    def clear_events(self):
        self.event_landed = None
        self.event_takeoff = None

    def get_properties(self) -> Dict[str, Any]:
        tags = []
        props = {}
        vdef = self.definition_index
        if vdef >= 0:
            mapped = typemap.get(self.definition_index, None)
            if mapped is not None:
                props["ShortName"] = mapped.shortname
                tags.extend(mapped.tags)
                if mapped.name_prefix:
                    props["Name"] = mapped.name_prefix
        if tags:
            props["Type"] = "+".join(tags)
        return props

    def is_unit(self) -> bool:
        return len(self.uid) and self.uid[0] == "u"

    def to_acmi(self):
        mapped = typemap.get(self.definition_index, None)

        items = []
        if self.uid[0] == "u":
            item_id = self.uid[1:]
            items.append(item_id)
        props = self.get_properties()
        if props:
            for name, value in props.items():
                items.append(f"{name}={value}")
        if self.x is not None:
            position = f"T={m2deg(self.x)}|{m2deg(self.y)}|"
            if self.alt is not None:
                position += f"{self.alt}"
            elif mapped and mapped.is_air():
                position += "10"
            position += "||"
            items.append(position)
        if self.team >= 0:
            color = "Orange"
            if self.team == 0:
                color = "Cyan"
            elif self.team == 1:
                color = "Red"
            elif self.team == 2:
                color = "Yellow"
            elif self.team == 3:
                color = "Green"
            elif self.team == 4:
                color = "Violet"
            items.append(f"Color={color}")
        detail = ",".join(items)
        return detail
