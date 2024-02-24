import subprocess
import argparse
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict

from cc2types import Unit
from cc2utils import logger


CC2 = Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Carrier Command 2\\carrier_command.exe")
parser = argparse.ArgumentParser(description="cc2 tacview adapter")
parser.add_argument("--run", default=False, action="store_true")
parser.add_argument("--verbose", default=False, action="store_true")
parser.add_argument("--load", type=Path,
                    help="convert a cc2 SAVE log to a tacview file",
                    metavar="SAVE")


MAP_ORIGIN_LAT = -5
MAP_ORIGIN_LON = -5


def get_last_file() -> Path:
    folder = Path.home() / "cc2-log"
    files = sorted(folder.glob("cc2-rac-raw-*.log"), key=lambda x: x.name)
    if len(files):
        return files[-1]
    assert False, "no files to convert"


def run_cc2(save_file: Path, verbose=False):
    cmdline = [str(CC2), "-dev"]
    logger.info("Starting cc2 ..")
    proc = subprocess.Popen(cmdline,
                            shell=False,
                            stderr=subprocess.STDOUT,
                            stdout=subprocess.PIPE,
                            cwd=CC2.parent,
                            encoding="utf-8",
                            )
    connected = False
    logger.info(f"Save tac data as: {save_file} ..")
    prev = None

    spins = ["/", "-", "\\"]
    spin_n = 0

    msg_count = 0
    last_count = 0
    last_rate = time.monotonic()

    def spinner(prefix, spin_n):
        print(f"\r{prefix} " + spins[spin_n], end=" ")
        spin_n = (1 + spin_n) % len(spins)
        return spin_n

    with open(save_file, "w") as outfile:
        while proc.poll() is None:
            line = proc.stdout.readline()

            now = time.monotonic()
            elapsed = now - last_rate
            last_rate = now
            if msg_count > 0 and elapsed > 0:
                rate = int((msg_count - last_count) / elapsed)
                prefix = f"{rate} msg/sec"
                spin_n = spinner(prefix, spin_n)
            last_count = msg_count

            if line == prev:
                continue
            if line.startswith("tac:"):
                msg_count += 1
                if not connected:
                    connected = True
                    logger.info("connected with stdout..")
                outfile.write(line)
                prev = line
                if verbose:
                    logger.info(line)

            elif line.startswith("log:"):
                logger.info(line.split(":", 1)[1].strip())
            else:
                if line.rstrip():
                    logger.info(line.rstrip())
    logger.info("cc2 has exited.")


def totacview(load_file: Path) -> Path:
    game_time = 0
    map_objects: Dict[str, Unit] = {}

    print(f"loading {load_file}..")
    lines = 0
    newfile = load_file.parent / (load_file.stem + ".acmi")
    with newfile.open("w") as outfile:
        with load_file.open("r") as infile:
            print("FileType=text/acmi/tacview", file=outfile)
            print("FileVersion=2.2", file=outfile)
            print(f"0,ReferenceLongitude={MAP_ORIGIN_LON}", file=outfile)
            print(f"0,ReferenceLatitude={MAP_ORIGIN_LAT}", file=outfile)

            for line in infile.readlines():
                if line.startswith("tac:"):
                    lines += 1
                    print(f"\r{lines} ", flush=True, end="")
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
                                new_game_time = float(props["t"])
                                if game_time == 0:
                                    print("0,ReferenceTime=2000-01-01T00:00:00Z", file=outfile)
                                print(f"t={new_game_time:4.2f}s  ", end="", flush=True)
                                if new_game_time > game_time:
                                    game_time = new_game_time
                                    # print all units so far
                                    for uid, u in map_objects.items():
                                        if u.last_printed < game_time:
                                            show = False
                                            if u.ttl > 0:
                                                if u.is_building():
                                                    show = True
                                                else:
                                                    u.ttl -= 1
                                                    if u.is_weapon():
                                                        show = True
                                                    elif u.is_explosion():
                                                        show = True
                                                    elif not u.docked:
                                                        if u.x is not None:
                                                            show = True
                                            if show:
                                                with u.reset():
                                                    events = u.get_events()
                                                    if u.has_changed():
                                                        print(u.to_acmi(remember=True), file=outfile)
                                                    if not u.printed_destroyed:
                                                        for event in events:
                                                            print(f"0,Event={event}|{u.map_id()}|", file=outfile)
                                                        if u.destroyed:
                                                            u.printed_destroyed = True
                                                u.last_printed = game_time

                                    for uid in list(map_objects.keys()):
                                        u = map_objects[uid]
                                        if u.ttl <= 0 or u.destroyed:

                                            if u.destroyed:
                                                blast = Unit(uid="x" + str(uuid.uuid4()), typ="x", x=u.x, y=u.y, alt=u.alt)
                                                blast.ttl = 10
                                                map_objects[blast.uid] = blast
                                            else:
                                                # simply went out of range
                                                print(f"0,Event=LeftArea|{u.map_id()}|", file=outfile)

                                            del map_objects[uid]
                                            print(f"-{u.map_id()}", file=outfile)

                                    print(f"#{new_game_time}", file=outfile)

                        elif len(parts) > 2:
                            item_id = parts[1]
                            item_def = props.get("def", None)
                            item_team = props.get("team", None)
                            if item_id not in map_objects:
                                u = Unit(uid=item_id,
                                         typ=item_def,
                                         team=item_team)
                                map_objects[item_id] = u

                            if props and item_id:
                                u = map_objects.get(item_id, None)
                                if u is not None:
                                    try:
                                        u.update(props, game_time)
                                        u.ttl = 2
                                    except:
                                        pass
    return newfile


def run():
    opts = parser.parse_args()
    if opts.run:
        savefile = Path.home() / "cc2-log" / f"cc2-rac-raw-{datetime.now().timestamp()}.log"
        savefile.parent.mkdir(parents=True, exist_ok=True)
        run_cc2(savefile, verbose=opts.verbose)
    elif opts.load:
        filename = opts.load
        if filename.name == "last":
            filename = get_last_file()

        newfile = totacview(filename)
        print(newfile)


if __name__ == "__main__":
    run()
