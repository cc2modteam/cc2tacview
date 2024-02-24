"""Type relationships with tacview and cc2"""
import contextlib
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
    # aircraft
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

    # ships
    0: CC2Item("CRR",
                 "Tarawa",
                 tags=["Heavy", "Sea", "Watercraft", "AircraftCarrier"]),
    16: CC2Item("BRG",
                "Cargo",
                tags=["Medium", "Sea", "Watercraft"]),
    77: CC2Item("NDL",
                "Perry",
                tags=["Light", "Sea", "Watercraft", "Warship"]),
    79: CC2Item("SWD",
                "Ticonderoga",
                tags=["Medium", "Sea", "Watercraft", "Warship"]),

    # ground units
    6: CC2Item("BER",
               "Tank",
               tags=["Vehicle", "Military", "Tank", "Unknown"]),
    2: CC2Item("SEL",
               "Jeep",
               tags=["Vehicle", "Car", "Jeep"]),
    4: CC2Item("WLR",
               "Humvee",
               tags=["Vehicle", "Car", "Humvee"]),
    88: CC2Item("MUL",
               "M818",
               tags=["Vehicle", "Truck", "M818"]),

    # jetty
    64: CC2Item("JETTY",
                "",
                tags=[]),

    # turrets
    59: CC2Item("TRT",
                "",
                tags=[]),

    # bombs
    52: CC2Item("Light Bomb",
                "",
                tags=["Light", "Bomb"]),
    53: CC2Item("Medium Bomb",
                "",
                tags=["Medium", "Bomb"]),
    54: CC2Item("Heavy Bomb",
                "",
                tags=["Heavy", "Bomb"]),

    # missiles
    44: CC2Item("Missile",
                "",
                tags=["Missile"]),
    45: CC2Item("Missile",
                "",
                tags=["Missile"]),
    46: CC2Item("Missile",
                "",
                tags=["Missile"]),
    47: CC2Item("AA Missile",
                "",
                tags=["Missile"]),
    48: CC2Item("Rocket",
                "",
                tags=["Missile"]),
    49: CC2Item("Cruise Missile",
                "",
                tags=["Missile"]),
    66: CC2Item("Torpedo",
                "",
                tags=["Torpedo"]),

    71: CC2Item("TV Missile",
                "",
                tags=["Missile"]),

}


@dataclasses.dataclass
class Record:
    t: float = 0.0
    value: Optional[float] = None


@dataclasses.dataclass
class Unit:
    uid: str = "x"
    typ: str = "-1"
    x: Optional[float] = None
    y: Optional[float] = None
    alt: Optional[float] = None
    hdg: Optional[float] = None
    team: int = -1
    last_printed: int = -1
    docked: bool = True
    event_takeoff: Optional[float] = None
    event_landed: Optional[float] = None
    ttl: int = 10
    destroyed: bool = False
    last_output: Optional[str] = None
    altitude_history: List[Record] = dataclasses.field(default_factory=list)

    printed_destroyed = False

    # building/island size
    ew = 0
    ns = 0
    h = 0
    name = ""

    def map_kind(self) -> str:
        return self.uid[0]

    def is_building(self) -> bool:
        if self.type_name == "JETTY":
            return True
        return self.map_kind() == "b"

    def is_weapon(self) -> bool:
        return self.map_kind() == "m"

    def map_id(self) -> str:
        id_hash = abs(hash(self.uid))
        return f"{id_hash:x}"

    def update(self, data: dict, t: float):
        for prop in ["x", "y", "alt", "hdg", "ns", "ew", "h"]:
            value = data.get(prop, None)
            if value is not None:
                setattr(self, prop, float(value))
        name = data.get("name", None)
        if name is not None:
            self.name = name
        team = data.get("team", None)
        if team is not None:
            self.team = int(team)
        if "destroyed" in data:
            self.destroyed = True

        if "docked" in data:
            docked_now = self.docked
            self.docked = data.get("docked") == "true"
            if docked_now != self.docked:
                if self.docked:
                    # landed
                    self.event_landed = t
                    self.event_takeoff = None
                else:
                    self.event_landed = None
                    self.event_takeoff = t

                    if self.is_air():
                        alt = Record(t=t, value=10)
                        self.altitude_history.append(alt)
                        self.alt = alt.value

    @property
    def definition_index(self) -> int:
        try:
            return int(self.typ)
        except ValueError:
            pass
        except TypeError:
            pass
        return None

    def has_changed(self) -> bool:
        current = self.to_acmi()
        return current != self.last_output

    def get_events(self) -> List[str]:
        events = []
        if self.is_air():
            if self.event_landed is not None:
                events.append("Landed")
            elif self.event_takeoff is not None:
                events.append("TakenOff")
        if self.destroyed:
            events.append("Destroyed")
        elif self.ttl < 1:
            events.append("LeftArea")
        return events

    def clear_events(self):
        self.event_landed = None
        self.event_takeoff = None

    def get_properties(self) -> Dict[str, Any]:
        tags = []
        props = {}
        if self.definition_index is not None:
            vdef = self.definition_index
            if vdef >= 0:
                mapped = typemap.get(self.definition_index, None)
                if self.type_name == "CRR":
                    props["RadarRange"] = 10000
                if self.type_name == "SWD":
                    props["RadarRange"] = 8000
                if self.type_name == "NDL":
                    props["RadarRange"] = 5000

                if mapped is not None:
                    props["ShortName"] = self.type_name + self.uid[1:]
                    tags.extend(mapped.tags)
                    if mapped.name_prefix:
                        props["Name"] = mapped.name_prefix

        if self.is_building():
            tags = ["Building"]

            if not self.h:
                if self.type_name == "JETTY":
                    props["Width"] = "200"
                    props["Length"] = "200"
                    props["Height"] = "42"
                else:
                    props["Width"] = "200"
                    props["Length"] = "200"
                    props["Height"] = "50"
            else:
                props["Width"] = str(self.ew)
                props["Length"] = str(self.ns)
                props["Height"] = str(self.h)
                if self.name:
                    props["Name"] = self.name

        if self.is_explosion():
            tags = ["Explosion"]
            props["Radius"] = "5"

        if tags:
            props["Type"] = "+".join(tags)
        return props

    def is_explosion(self):
        return self.map_kind() == "x"

    @property
    def type_name(self) -> str:
        if self.definition_index is not None:
            vdef = self.definition_index
            if vdef >= 0:
                mapped = typemap.get(self.definition_index, None)
                if mapped is not None:
                    return mapped.shortname
        if self.is_explosion():
            return "<BOOM>"
        return "?"

    def is_unit(self) -> bool:
        return len(self.uid) and self.uid[0] == "u"

    def is_air(self) -> bool:
        mapped = self.get_mapped()
        return mapped and mapped.is_air()

    def is_ship(self) -> bool:
        mapped = self.get_mapped()
        return mapped and mapped.is_ship()

    def get_mapped(self) -> Optional[CC2Item]:
        return typemap.get(self.definition_index, None)

    @contextlib.contextmanager
    def reset(self):
        try:
            yield
        finally:
            self.clear_events()
            self.hdg = None

    def to_acmi(self, remember=False):
        items = [str(self.map_id())]
        props = self.get_properties()

        if props:
            if self.last_printed < 0:
                for name, value in props.items():
                    items.append(f"{name}={value}")
        if self.x is not None:
            position = f"T={m2deg(self.x)}|{m2deg(self.y)}|"
            if self.alt is None:
                position += ""
            else:
                position += f"{self.alt}"
            items.append(position)
        if self.team is not None and self.team >= 0:
            color = "Orange"
            if self.team == 0:
                color = "Red"
            elif self.team == 1:
                color = "Cyan"
            elif self.team == 2:
                color = "Yellow"
            elif self.team == 3:
                color = "Green"
            elif self.team == 4:
                color = "Violet"
            items.append(f"Color={color}")
        detail = ",".join(items)
        if remember:
            self.last_output = detail
        return detail

    def __str__(self):
        return f"{self.type_name} {self.uid}"