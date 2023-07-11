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
                tags=[])

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
    ttl: int = 2

    altitude_history: List[Record] = dataclasses.field(default_factory=list)

    def map_kind(self) -> str:
        return self.uid[0]

    def is_explosion(self) -> bool:
        return self.map_kind() == "x"

    def is_building(self) -> bool:
        if self.type_name == "JETTY":
            return True
        return self.map_kind() == "b"

    def is_weapon(self) -> bool:
        return self.map_kind() == "w"

    def map_id(self) -> int:
        value = int(self.uid[1:])
        kind = self.map_kind()
        if self.is_building():
            return (1 + value) << 16
        elif kind == "x":
            # explosion
            return (1 + value) << 32
        elif kind == "w":
            # explosion
            return (1 + value) << 48
        return 1 + value

    def update(self, data: dict, t: float):
        for prop in ["x", "y", "alt", "hdg"]:
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
        except TypeError:
            return -1

    def get_events(self) -> List[str]:
        events = []
        if self.is_air():
            if self.event_landed is not None:
                events.append("Landed")
            elif self.event_takeoff is not None:
                events.append("TakenOff")
        if self.ttl < 1:
            events.append("Destroyed")
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
                if mapped is not None:
                    props["ShortName"] = self.type_name
                    tags.extend(mapped.tags)
                    if mapped.name_prefix:
                        props["Name"] = mapped.name_prefix

        if self.is_building():
            tags = ["Building"]

        if tags:
            props["Type"] = "+".join(tags)
        return props

    @property
    def type_name(self) -> str:
        if self.definition_index is not None:
            vdef = self.definition_index
            if vdef >= 0:
                mapped = typemap.get(self.definition_index, None)
                if mapped is not None:
                    return mapped.shortname
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

    def to_acmi(self):
        items = [str(self.map_id())]
        props = self.get_properties()
        if self.is_building():
            if self.type_name == "JETTY":
                props["Radius"] = "100"

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
            # heading not working quite right
            # if self.is_ship():
                # hdg = ""
                # if self.hdg is not None:
                #     hdg = self.hdg
                # position += f"|||{hdg}"
            items.append(position)
        if self.team >= 0:
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
        return detail
