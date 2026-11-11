"""Download official 2024 source data. Resume safely; never pad data size."""
from __future__ import annotations

import argparse
import calendar
import concurrent.futures
import hashlib
import gzip
import json
from pathlib import Path
import ssl
import threading
import time
from datetime import datetime, timezone, date, timedelta
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import zipfile

import certifi

ROOT = Path(__file__).resolve().parents[1]
CTX = ssl.create_default_context(cafile=certifi.where())
LOCK = threading.Lock()
TAXI = "https://data.cityofchicago.org/resource/ajtu-isnz.json"
FIELDS = ["trip_id", "trip_start_timestamp", "trip_end_timestamp", "trip_seconds",
          "trip_miles", "pickup_community_area", "dropoff_community_area",
          "fare", "trip_total", "payment_type"]
RAW = ROOT / "data/raw"
LOG = ROOT / "docs/collection_log.jsonl"


def log(**row):
    row["collected_at_utc"] = datetime.now(timezone.utc).isoformat()
    with LOCK:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps({k: v for k, v in row.items() if k != "url"}, ensure_ascii=False), flush=True)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, dest, source, retries=4, fallback_urls=()):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        log(source=source, path=str(dest.relative_to(ROOT)), status="reused", bytes=dest.stat().st_size)
        return dest
    partial = dest.with_name(dest.name + ".partial")
    urls = [url, *fallback_urls]
    for attempt in range(retries):
        started = time.monotonic()
        current_url = urls[attempt % len(urls)]
        try:
            resumable = dest.suffix == ".zip"
            offset = partial.stat().st_size if resumable and partial.exists() else 0
            headers = {"User-Agent": "UniversityCourseProject/1.0 (public open data research)",
                       "Accept-Encoding": "identity" if resumable else "gzip"}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            req = Request(current_url, headers={"User-Agent": "UniversityCourseProject/1.0 (public open data research)",
                                        **headers})
            with urlopen(req, context=CTX, timeout=180) as r:
                status = r.status
                content_type = r.headers.get("Content-Type", "")
                expected = r.headers.get("Content-Length")
                encoding = r.headers.get("Content-Encoding", "")
                if offset and status == 206 and not r.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                    raise IOError("Unexpected range response; refusing to append mismatched bytes")
                if offset and status != 206:
                    offset = 0
                stream = gzip.GzipFile(fileobj=r) if encoding == "gzip" else r
                with partial.open("ab" if offset else "wb") as f:
                    while True:
                        # Persist smaller increments on unreliable connections.
                        chunk = stream.read(32 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
            size = partial.stat().st_size
            if expected and encoding != "gzip" and size - offset != int(expected):
                raise IOError(f"Incomplete response: {size - offset} != {expected}")
            if size == 0:
                raise IOError("Empty response")
            partial.replace(dest)
            log(source=source, url=current_url, path=str(dest.relative_to(ROOT)), status="downloaded",
                http_status=status, content_type=content_type, bytes=size, sha256=sha(dest),
                content_encoding=encoding, transfer_content_length=expected, resumed_from=offset,
                seconds=round(time.monotonic() - started, 2))
            return dest
        except Exception as e:
            if dest.suffix != ".zip":
                partial.unlink(missing_ok=True)
            delay = min(2 ** (attempt + 1), 16)
            if isinstance(e, HTTPError) and e.code in [429, 502, 503, 504]:
                retry_after = e.headers.get("Retry-After", "60" if e.code == 429 else "30")
                try:
                    delay = max(delay, int(retry_after))
                except ValueError:
                    delay = max(delay, 60)
            log(source=source, url=current_url, status="retry", attempt=attempt + 1, error=str(e), wait_seconds=delay)
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def taxi_day(day):
    start = day.isoformat() + "T00:00:00"
    end = (day + timedelta(days=1)).isoformat() + "T00:00:00"
    where = f"trip_start_timestamp >= '{start}' AND trip_start_timestamp < '{end}'"
    dest = RAW / "taxi" / f"taxi_{day.isoformat()}.json"
    if not dest.exists():
        pages, after, total = [], None, 0
        page_size = 5000
        while True:
            page_where = where if after is None else where + " AND trip_id > '" + after.replace("'", "''") + "'"
            query = urlencode({"$select": ",".join(FIELDS), "$where": page_where,
                               "$order": "trip_id ASC", "$limit": page_size})
            page = ROOT / "data/downloads/taxi_pages" / day.isoformat() / f"page_{len(pages):04d}.json"
            fetch(TAXI + "?" + query, page, "chicago_taxi_page")
            part = json.loads(page.read_bytes())
            if not isinstance(part, list) or len(part) > page_size:
                raise ValueError("Unexpected taxi page or ignored page limit")
            ids = [r["trip_id"] for r in part]
            if ids != sorted(set(ids)) or (after is not None and ids and ids[0] <= after):
                raise ValueError("Taxi page IDs are not strictly increasing")
            if any(not r["trip_start_timestamp"].startswith(day.isoformat()) for r in part):
                raise ValueError("Taxi page contains a record outside its requested day")
            pages.append(page)
            total += len(part)
            if len(part) < page_size:
                break
            after = ids[-1]
        # Retain original object bytes, only joining the response arrays. Cached
        # pages are transfer/source snapshots and never counted a second time.
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_name(dest.name + ".partial")
        with partial.open("wb") as out:
            out.write(b"[")
            first = True
            for page in pages:
                body = page.read_bytes().strip()[1:-1].strip()
                if body:
                    if not first:
                        out.write(b",")
                    out.write(body)
                    first = False
            out.write(b"]")
        if len(json.loads(partial.read_bytes())) != total:
            raise ValueError("Taxi day assembly lost or duplicated rows")
        partial.replace(dest)
        log(source="chicago_taxi", day=day.isoformat(), status="assembled", rows=total,
            pages=len(pages), path=str(dest.relative_to(ROOT)), bytes=dest.stat().st_size,
            sha256=sha(dest), representation="original API page objects joined into one daily array")
    else:
        log(source="chicago_taxi", path=str(dest.relative_to(ROOT)), status="reused", bytes=dest.stat().st_size)
    rows = json.loads(dest.read_bytes())
    if not isinstance(rows, list) or any(not r["trip_start_timestamp"].startswith(day.isoformat()) for r in rows):
        raise ValueError("Unexpected taxi daily response or incorrect date")
    log(source="chicago_taxi", day=day.isoformat(), status="parsed", rows=len(rows))


def validate_taxi_month(month):
    start = f"2024-{month:02d}-01T00:00:00"
    end = f"2024-{month + 1:02d}-01T00:00:00" if month < 12 else "2025-01-01T00:00:00"
    where = f"trip_start_timestamp >= '{start}' AND trip_start_timestamp < '{end}'"
    paths = sorted((RAW / "taxi").glob(f"taxi_2024-{month:02d}-??.json"))
    if len(paths) != calendar.monthrange(2024, month)[1]:
        raise ValueError(f"Missing daily files in taxi month {month}")
    n = sum(len(json.loads(p.read_bytes())) for p in paths)
    count_dest = ROOT / "data/metadata" / f"taxi_count_2024-{month:02d}.json"
    fetch(TAXI + "?" + urlencode({"$select": "count(*) as n", "$where": where}), count_dest, "chicago_taxi_count")
    expected = int(json.loads(count_dest.read_bytes())[0]["n"])
    if n != expected:
        raise ValueError(f"Taxi month {month}: downloaded {n}, expected {expected}")
    log(source="chicago_taxi", month=month, status="validated", rows=n)


def divvy_month(month):
    name = f"2024{month:02d}-divvy-tripdata.zip"
    archive = ROOT / "data/downloads" / name
    fetch("https://divvy-tripdata.s3.us-east-1.amazonaws.com/" + name, archive, "divvy_archive",
          fallback_urls=["https://divvy-tripdata.s3.amazonaws.com/" + name])
    with zipfile.ZipFile(archive) as z:
        members = [i for i in z.infolist() if i.filename.lower().endswith(".csv")
                   and not i.filename.startswith("__MACOSX/")]
        if not members:
            raise ValueError(f"No CSV in {archive}")
        for member in members:
            dest = RAW / "divvy" / Path(member.filename).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.stat().st_size == member.file_size:
                continue
            partial = dest.with_name(dest.name + ".partial")
            with z.open(member) as f, partial.open("wb") as out:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    out.write(chunk)
            if partial.stat().st_size != member.file_size:
                raise IOError("Truncated extracted CSV")
            partial.replace(dest)
            log(source="divvy", path=str(dest.relative_to(ROOT)), status="extracted",
                bytes=dest.stat().st_size, sha256=sha(dest), archive=str(archive.relative_to(ROOT)))


def auxiliaries():
    meta = ROOT / "data/metadata"
    fetch("https://data.cityofchicago.org/api/views/ajtu-isnz.json", meta / "taxi_schema.json", "taxi_metadata")
    fetch("https://divvybikes.com/system-data", meta / "divvy_source.html", "divvy_metadata")
    fetch("https://divvybikes.com/data-license-agreement", meta / "divvy_license.html", "divvy_license")
    fetch("https://data.cityofchicago.org/resource/igwz-8jzy.geojson?$limit=100", RAW / "boundaries/community_areas.geojson", "chicago_boundaries")
    query = urlencode({"dataset": "daily-summaries", "stations": "USW00094846,USW00014819",
                       "startDate": "2024-01-01", "endDate": "2024-12-31", "format": "json",
                       "units": "metric", "includeAttributes": "true", "includeStationName": "true",
                       "dataTypes": "PRCP,TMAX,TMIN,SNOW,AWND"})
    fetch("https://www.ncei.noaa.gov/access/services/data/v1?" + query, RAW / "weather/noaa_2024.json", "noaa")
    fetch("https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/", RAW / "holidays/opm_holidays.html", "opm")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["all", "divvy", "taxi", "aux"], default="all")
    p.add_argument("--months", nargs="+", type=int, default=list(range(1, 13)))
    p.add_argument("--workers", type=int, default=2)
    args = p.parse_args()
    if any(m < 1 or m > 12 for m in args.months):
        p.error("months must be 1..12")
    jobs = []
    if args.source in ["all", "divvy"]:
        jobs += [(divvy_month, m) for m in args.months]
    if args.source in ["all", "taxi"]:
        jobs += [(taxi_day, date(2024, m, d)) for m in args.months for d in range(1, calendar.monthrange(2024, m)[1] + 1)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fn, m) for fn, m in jobs]
        if args.source in ["all", "aux"]:
            futures.append(pool.submit(auxiliaries))
        failures = []
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
            except Exception as e:
                failures.append(str(e))
                log(status="partition_failed", scope=args.source, error=str(e))
    if failures:
        raise RuntimeError(f"{len(failures)} partitions failed; complete files are preserved. Rerun the same collection command.")
    if args.source in ["all", "taxi"]:
        for month in args.months:
            validate_taxi_month(month)
    log(status="collection_completed", scope=args.source)


if __name__ == "__main__":
    main()
