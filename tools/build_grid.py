"""Download NASA POWER monthly grids and pack them as seasonal means for the browser.

Usage:
    python3 tools/build_grid.py raw data

POWER's regional endpoint returns one parameter for a box of at most 10 x 10 degrees,
so the area is fetched in tiles (cached in raw/). For every grid cell and year we keep
five seasonal means (year, DJF, MAM, JJA, SON); the page computes the trend statistics
itself, so the user can change season and period without a server.

data/<VAR>.bin: little-endian int16, [cell][season][year], value * scale, -32768 = missing.
data/grid.json: grid geometry, years, units and scale per variable.
"""
import json
import math
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

LAT0, LAT1, LON0, LON1 = 34, 64, -12, 48
Y0, Y1 = 1981, 2025
VARS = {
    # name: (community, scale)
    "T2M": ("AG", 100),
    "PRECTOTCORR": ("AG", 100),
    "GWETROOT": ("AG", 10000),
    "SNODP": ("AG", 10),
    "ALLSKY_SFC_SW_DWN": ("RE", 100),
}
API = "https://power.larc.nasa.gov/api/temporal/monthly/regional"
SEASONS = {"ANN": range(1, 13), "DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJA": (6, 7, 8), "SON": (9, 10, 11)}


def tiles():
    for la in range(LAT0, LAT1, 10):
        for lo in range(LON0, LON1, 10):
            yield la, min(la + 10, LAT1), lo, min(lo + 10, LON1)


def fetch(var, box, raw):
    la0, la1, lo0, lo1 = box
    path = os.path.join(raw, f"{var}_{la0}_{lo0}.json")
    if os.path.exists(path):
        return path
    url = (f"{API}?parameters={var}&community={VARS[var][0]}&latitude-min={la0}&latitude-max={la1}"
           f"&longitude-min={lo0}&longitude-max={lo1}&start={Y0}&end={Y1}&format=JSON")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                body = r.read()
            json.loads(body)["features"]
            with open(path, "wb") as fh:
                fh.write(body)
            return path
        except Exception as e:  # POWER is occasionally busy; back off and retry
            print(f"  {var} {box}: {e}, retry {attempt + 1}", flush=True)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"{var} {box} failed")


def build(var, raw, out):
    paths = [fetch(var, b, raw) for b in tiles()]
    cells, units = {}, ""
    for p in paths:
        d = json.load(open(p))
        units = d["parameters"][var]["units"]
        for f in d["features"]:
            lon, lat = f["geometry"]["coordinates"][:2]
            cells[(round(lat, 4), round(lon, 4))] = f["properties"]["parameter"][var]
    lats = sorted({k[0] for k in cells})
    lons = sorted({k[1] for k in cells})
    years = list(range(Y0, Y1 + 1))
    scale = VARS[var][1]
    buf = bytearray()
    for la in lats:
        for lo in lons:
            v = cells.get((la, lo), {})
            for months in SEASONS.values():
                for y in years:
                    vals = []
                    for m in months:
                        yy = y - 1 if (m == 12 and len(months) == 3) else y  # DJF: December of the year before
                        x = v.get(f"{yy}{m:02d}", -999)
                        if x is None or x <= -999:
                            vals = None
                            break
                        vals.append(x)
                    q = -32768 if not vals else max(-32767, min(32767, round(sum(vals) / len(vals) * scale)))
                    buf += q.to_bytes(2, "little", signed=True)
    with open(os.path.join(out, f"{var}.bin"), "wb") as fh:
        fh.write(buf)
    step = lambda a: round((a[-1] - a[0]) / (len(a) - 1), 4)
    print(f"{var}: {len(lats)}x{len(lons)} cells, {len(buf) / 1e6:.1f} MB, {units}", flush=True)
    return {"lat0": lats[0], "dlat": step(lats), "nlat": len(lats),
            "lon0": lons[0], "dlon": step(lons), "nlon": len(lons), "scale": scale, "units": units}


def main(raw, out):
    os.makedirs(raw, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    jobs = [(v, b) for v in VARS for b in tiles()]
    with ThreadPoolExecutor(3) as ex:  # be gentle with the public API
        list(ex.map(lambda j: fetch(j[0], j[1], raw), jobs))
    meta = {"years": [Y0, Y1], "seasons": list(SEASONS), "vars": {v: build(v, raw, out) for v in VARS}}
    json.dump(meta, open(os.path.join(out, "grid.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
