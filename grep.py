import json
import hashlib
import logging
import os
from collections import defaultdict
from glob import glob
from urllib.request import urlopen, Request

URL = "https://opravujeme.to/api/action/"
TDIR = "data"

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)

    existing_ids, new_ids, removed_ids = set(), set(), set()
    existing_hashes = dict()

    os.makedirs(TDIR, exist_ok=True)
    existing_data = dict()
    for filename in glob(os.path.join(TDIR, "*.json")):
        with open(filename) as f:
            existing_data.update({j["id"]: j for j in json.load(f)})
    existing_ids = set(existing_data.keys())
    logging.info("Nahral jsem %d ids z existujiciho dumpu", len(existing_ids))

    qs = "?limit=100"
    data = []
    total = None
    while True:
        r = Request(URL + qs)
        logging.info("oteviram %s", r.full_url)
        with urlopen(r) as req:
            page = json.load(req)
            data.extend(page["objects"])
            if not total:
                total = page["meta"]["total_count"]

            if not page["meta"]["next"]:
                break
            qs = page["meta"]["next"]

    if len(data) != total:
        raise IOError(f"cekali jsme {total} elementu, mame {len(data)}")

    downloaded_data = {j["id"]: j for j in data}
    downloaded_ids = set(downloaded_data.keys())
    data.sort(key=lambda x: x["id"])

    new_ids = downloaded_ids - existing_ids
    removed_ids = existing_ids - downloaded_ids

    changelog = []
    stats = [len(new_ids), len(removed_ids), 0]

    for new_id in sorted(new_ids):
        changelog.append(f"Přidáno: {downloaded_data[new_id]['name']}")

    for removed_id in sorted(removed_ids):
        changelog.append(f"Odebráno: {existing_data[removed_id]['name']}")

    for el in data:
        el["sha1"] = hashlib.sha1(json.dumps(el).encode()).hexdigest()
        if el["id"] in existing_data and el["sha1"] != existing_data[el["id"]]["sha1"]:
            changelog.append(f"Změněno: {el['name']}")
            stats[2] += 1

    logging.info("Ukladam %d elementu do %s", len(data), TDIR)
    by_district = defaultdict(list)
    for el in data:
        dss = el["city_part"]
        if not dss:
            by_district["ostatni"].append(el)
        else:
            for ds in dss:
                by_district[ds].append(el)

    for ds, dt in by_district.items():
        if ds.isdigit():
            ds = ds.rjust(2, "0")
        dt.sort(key=lambda x: x["id"])
        with open(os.path.join(TDIR, f"praha-{ds}.json"), "wt", encoding="utf-8") as fw:
            json.dump(dt, fw, indent=2, sort_keys=True, ensure_ascii=False)

    if len(changelog) > 0:
        total = sum(stats)
        print(
            f"Nové: {stats[0]}, zrušené: {stats[1]}, změněné: {stats[2]}. Celkem: {total}"
        )
        print("\n".join(sorted(changelog)))
