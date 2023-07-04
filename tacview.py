import dataclasses
import subprocess
import argparse
from datetime import  datetime
from io import TextIOBase

from pathlib import Path
from typing import Dict, Optional, Any

CC2 = Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Carrier Command 2\\carrier_command.exe")
parser = argparse.ArgumentParser(description="cc2 tacview adapter")
parser.add_argument("--run", default=False, action="store_true")
parser.add_argument("--load", type=Path,
                    help="convert a cc2 SAVE log to a tacview file",
                    metavar="SAVE")


def m2deg(m: float) -> float:
    """meters to degrees north"""
    nm = m / 1852.0
    deg = nm / 60.0
    return deg


def run_cc2(save_file: Path):
    cmdline = [str(CC2)]
    proc = subprocess.Popen(cmdline,
                            stdout=subprocess.PIPE,
                            cwd=CC2.parent,
                            encoding="utf-8",
                            )
    with open(save_file, "w") as outfile:
        while proc.poll() is None:
            line = proc.stdout.readline()
            if line.startswith("tac:"):
                outfile.write(line)


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
    ttl: int = 2

    def update(self, data: dict):
        for prop in ["x", "y", "alt"]:
            value = data.get(prop, None)
            if value is not None:
                setattr(self, prop, float(value))
        team = data.get("team", None)
        if team is not None:
            self.team = int(team)
        if "docked" in data:
            self.docked = data.get("docked") == "true"

    @property
    def definition_index(self) -> int:
        return int(self.typ)

    def get_properties(self) -> Dict[str, Any]:
        tags = []
        props = {}
        vdef = self.definition_index
        if vdef >= 0:
            if vdef == 0:
                props["ShortName"] = "CRR"
                tags.extend(["Heavy", "Sea", "Watercraft", "AircraftCarrier"])
            elif vdef == 8:
                props["ShortName"] = "ALB"
                tags.extend(["Light", "Air", "FixedWing"])
            elif vdef == 10:
                props["ShortName"] = "MNT"
                tags.extend(["Medium", "Air", "FixedWing"])
            elif vdef == 12:
                props["ShortName"] = "RZR"
                tags.extend(["Light", "Air", "Rotorcraft"])
            elif vdef == 14:
                props["ShortName"] = "PTR"
                tags.extend(["Medium", "Air", "Rotorcraft"])

        if tags:
            props["Type"] = "+".join(tags)
        return props

    def to_acmi(self):
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


def totacview(load_file: Path) -> Path:
    game_time = 0
    units: Dict[str, Unit] = {}

    newfile = load_file.parent / (load_file.stem + ".acmi")
    with newfile.open("w") as outfile:
        with load_file.open("r") as infile:
            print("FileType=text/acmi/tacview", file=outfile)
            print("FileVersion=2.2", file=outfile)

            for line in infile.readlines():
                if line.startswith("tac:"):
                    line = line.strip()
                    parts = line.split(":")
                    if len(parts) > 1:
                        props = {}
                        for part in parts[1:]:
                            values = part.split(",")
                            for item in values:
                                if "=" in item:
                                    pname, pvalue = item.split("=", 1)
                                    props[pname] = pvalue

                        if len(parts) == 2:
                            if "t" in props:
                                # time sync
                                new_game_time = int(props["t"])
                                if game_time == 0:
                                    print("0,ReferenceTime=2000-01-01T00:00:00Z", file=outfile)
                                if new_game_time > game_time:
                                    game_time = new_game_time
                                    # print all units so far
                                    for u in units.values():
                                        if u.last_printed < game_time:
                                            if u.ttl > 0:
                                                u.last_printed = game_time
                                                if not u.docked:
                                                    if u.x is not None:
                                                        print(u.to_acmi(), file=outfile)
                                                        u.x = None
                                                        u.y = None
                                                        u.alt = None

                                    print(f"#{new_game_time}.0", file=outfile)

                        elif len(parts) > 3:
                            item_id = parts[2]
                            item_def = props.get("def", None)
                            item_team = props.get("team", None)
                            if item_id not in units:
                                u = Unit(uid=item_id,
                                         typ=item_def,
                                         team=item_team)
                                units[item_id] = u

                            if props and item_id:
                                u = units.get(item_id, None)
                                if u is not None:
                                    u.update(props)
                                u.ttl = 2
    return newfile


def run():
    opts = parser.parse_args()
    if opts.run:
        savefile = Path.home() / "cc2-log" / f"cc2-rac-raw-{datetime.now().timestamp()}.log"
        savefile.parent.mkdir(parents=True, exist_ok=True)
        run_cc2(savefile)
    elif opts.load:
        newfile = totacview(opts.load)
        print(newfile)


if __name__ == "__main__":
    run()
