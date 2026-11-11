"""Build cleaned trip files and validated daily/community-day integrations."""
from __future__ import annotations

from collections import Counter
import gzip
import json
from pathlib import Path
import re
import time

from lxml import html
import numpy as np
import pandas as pd
from shapely import STRtree, points
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
CLEAN = ROOT / "data/cleaned"
OUT = ROOT / "data/integrated"
SAMPLE = ROOT / "data/samples"
DATES = pd.date_range("2024-01-01", "2024-12-31", freq="D")


def dump(obj, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def parse_holidays():
    tree = html.fromstring((RAW / "holidays/opm_holidays.html").read_bytes())
    # OPM uses one year-specific table. Do not hardcode or infer dates from a package.
    tables = tree.xpath("//table[@id='2024']")
    if not tables:
        tables = [t for t in tree.xpath("//table") if "2024 Holiday Schedule" in t.text_content()]
    if len(tables) != 1:
        # Some versions put the year on the parent tab container.
        tables = tree.xpath("//*[@id='2024']//table")
    if len(tables) != 1:
        raise ValueError("Cannot uniquely identify OPM's 2024 table")
    rows = []
    for tr in tables[0].xpath(".//tr"):
        cells = [" ".join(c.text_content().split()) for c in tr.xpath("./td")]
        if len(cells) < 2:
            continue
        text = re.sub(r"\*+", "", cells[0]).strip()
        date = pd.to_datetime(text + " 2024", format="%A, %B %d %Y")
        rows.append({"date": date.strftime("%Y-%m-%d"), "holiday_name": cells[1]})
    df = pd.DataFrame(rows)
    if len(df) != 11 or df.date.duplicated().any():
        raise ValueError(f"Unexpected OPM calendar: {len(df)} holidays")
    df.to_csv(CLEAN / "holidays_2024.csv", index=False)
    return df


def weather():
    raw = pd.DataFrame(json.loads((RAW / "weather/noaa_2024.json").read_bytes()))
    fields = ["PRCP", "TMAX", "TMIN", "SNOW", "AWND"]
    rejected = {}
    for field in fields:
        raw[field] = pd.to_numeric(raw.get(field), errors="coerce")
        # NOAA attributes: measurement flag, quality flag, source flag, observation time.
        attrs = raw.get(field + "_ATTRIBUTES", pd.Series("", index=raw.index)).fillna("")
        flags = attrs.str.split(",").str[1].fillna("").ne("")
        rejected[field] = int(flags.sum())
        raw.loc[flags, field] = np.nan
    raw["date"] = pd.to_datetime(raw.DATE).dt.normalize()
    if raw.duplicated(["date", "STATION"]).any():
        raise ValueError("Duplicate station-day weather records")
    raw.to_csv(CLEAN / "weather_station_days.csv", index=False)
    daily = raw.groupby("date")[fields].mean().reindex(DATES)
    daily.index.name = "date"
    daily = daily.rename(columns={"PRCP": "precip_mm", "TMAX": "tmax_c", "TMIN": "tmin_c",
                                   "SNOW": "snow_mm", "AWND": "wind_mps"})
    daily["tavg_c"] = (daily.tmax_c + daily.tmin_c) / 2
    daily["weather_stations"] = raw.groupby("date").size().reindex(DATES, fill_value=0)
    daily["rain_day"] = daily.precip_mm.ge(1).where(daily.precip_mm.notna())
    daily.to_csv(CLEAN / "weather_daily.csv")
    dump({"station_rows": len(raw), "station_ids": sorted(raw.STATION.unique()),
          "days": len(daily), "rejected_quality_flags": rejected,
          "daily_missing": {k: int(v) for k, v in daily.isna().sum().items()}}, ROOT / "docs/weather_quality.json")
    return daily.reset_index()


class AreaLookup:
    def __init__(self):
        self.geo = json.loads((RAW / "boundaries/community_areas.geojson").read_bytes())
        self.ids = np.array([int(f["properties"]["area_numbe"]) for f in self.geo["features"]])
        self.names = {int(f["properties"]["area_numbe"]): f["properties"]["community"] for f in self.geo["features"]}
        self.shapes = [shape(f["geometry"]) for f in self.geo["features"]]
        if len(self.ids) != 77 or len(set(self.ids)) != 77 or not all(s.is_valid for s in self.shapes):
            raise ValueError("Invalid community geography")
        self.tree = STRtree(self.shapes)

    def map(self, lon, lat):
        result = np.full(len(lon), np.nan)
        valid = np.isfinite(lon) & np.isfinite(lat)
        idx = np.flatnonzero(valid)
        if len(idx):
            pair = self.tree.query(points(lon[valid], lat[valid]), predicate="within")
            if len(np.unique(pair[0])) != len(pair[0]):
                raise ValueError("Point matched more than one community")
            result[idx[pair[0]]] = self.ids[pair[1]]
        return result


def clean_and_aggregate(mode, areas, *, source_paths=None, dates=None, full_year=True):
    source_paths = sorted(source_paths if source_paths is not None else (RAW / mode).glob("*.csv" if mode == "divvy" else "*.json"))
    dates = DATES if dates is None else dates
    expected_files = 12 if mode == "divvy" else 366
    if full_year and len(source_paths) != expected_files:
        raise ValueError(f"{mode} needs {expected_files} complete files for 2024, found {len(source_paths)}")
    sums, hours, communities = [], [], []
    quality = []
    raw_samples, cleaned_samples = [], []
    seen = set()
    for file_index, source in enumerate(source_paths):
        start = time.monotonic()
        counts = Counter()
        dest = CLEAN / mode / (source.stem + ".csv.gz")
        dest.parent.mkdir(parents=True, exist_ok=True)
        chunks = pd.read_csv(source, chunksize=150000, dtype=str) if mode == "divvy" else [pd.DataFrame(json.loads(source.read_bytes()))]
        first = True
        with gzip.open(dest, "wt", encoding="utf-8", compresslevel=1, newline="") as target:
            for raw in chunks:
                counts["raw_rows"] += len(raw)
                rid = "ride_id" if mode == "divvy" else "trip_id"
                sampled_raw = raw.sample(n=min(5, len(raw)), random_state=42).copy()
                sampled_ids = set(sampled_raw[rid])
                sampled_raw["_source_file"] = source.name
                raw_samples.append(sampled_raw)
                startcol = "started_at" if mode == "divvy" else "trip_start_timestamp"
                endcol = "ended_at" if mode == "divvy" else "trip_end_timestamp"
                df = pd.DataFrame(index=raw.index)
                df["trip_id"] = raw[rid]
                df["started_at"] = pd.to_datetime(raw[startcol], errors="coerce", format="mixed")
                df["ended_at"] = pd.to_datetime(raw[endcol], errors="coerce", format="mixed")
                df["duration_seconds"] = ((df.ended_at - df.started_at).dt.total_seconds() if mode == "divvy"
                                              else pd.to_numeric(raw.trip_seconds, errors="coerce"))
                keep = df.trip_id.notna() & df.started_at.notna()
                counts["removed_missing_id_or_start"] += int((~keep).sum())
                inyear = df.started_at.ge("2024-01-01") & df.started_at.lt("2025-01-01")
                counts["removed_outside_year"] += int((keep & ~inyear).sum())
                keep &= inyear
                if mode == "divvy":
                    bicycle = raw.rideable_type.isin(["classic_bike", "electric_bike"])
                    counts["removed_non_bicycle"] += int((keep & ~bicycle).sum())
                    keep &= bicycle
                already_seen = np.fromiter((x in seen for x in df.trip_id), dtype=bool, count=len(df))
                duplicate = df.trip_id.where(keep).duplicated() | already_seen
                counts["removed_duplicate_id"] += int((keep & duplicate).sum())
                keep &= ~duplicate
                # Register IDs before duration filtering so duplicates cannot re-enter later.
                seen.update(df.loc[keep, "trip_id"])
                good_duration = df.duration_seconds.between(60, 86400)
                counts["removed_duration_missing_or_outside_60_86400"] += int((keep & ~good_duration).sum())
                keep &= good_duration
                if mode == "divvy":
                    lon = pd.to_numeric(raw.start_lng, errors="coerce").to_numpy()
                    lat = pd.to_numeric(raw.start_lat, errors="coerce").to_numpy()
                    df["community_id"] = areas.map(lon, lat)
                    df["rider_type"] = raw.member_casual
                    df["rideable_type"] = raw.rideable_type
                    df["payment_type"] = ""
                    df["distance_miles"] = np.nan
                    df["fare_usd"] = np.nan
                    df["trip_total_usd"] = np.nan
                else:
                    df["community_id"] = pd.to_numeric(raw.get("pickup_community_area"), errors="coerce")
                    df.loc[~df.community_id.isin(areas.ids), "community_id"] = np.nan
                    df["rider_type"] = ""
                    df["rideable_type"] = ""
                    df["payment_type"] = raw.get("payment_type", "")
                    for orig, new, lower, upper in [("trip_miles", "distance_miles", 0.001, 200),
                                                    ("fare", "fare_usd", 0, 1000),
                                                    ("trip_total", "trip_total_usd", 0, 1000)]:
                        val = pd.to_numeric(raw.get(orig), errors="coerce")
                        valid = val.between(lower, upper)
                        counts["invalid_" + new] += int((keep & ~valid).sum())
                        df[new] = val.where(valid)
                df = df.loc[keep].copy()
                df["date"] = df.started_at.dt.normalize()
                df["hour"] = df.started_at.dt.hour
                counts["cleaned_rows"] += len(df)
                counts["unmatched_community_rows"] += int(df.community_id.isna().sum())
                df.to_csv(target, index=False, header=first, date_format="%Y-%m-%d %H:%M:%S.%f")
                sampled_clean = df[df.trip_id.isin(sampled_ids)].copy()
                sampled_clean["_source_file"] = source.name
                cleaned_samples.append(sampled_clean)
                sums.append(df.groupby("date").agg(trips=("trip_id", "size"), duration_sum=("duration_seconds", "sum"),
                                                    miles_sum=("distance_miles", "sum"), miles_n=("distance_miles", "count"),
                                                    fare_sum=("fare_usd", "sum"), fare_n=("fare_usd", "count")))
                hours.append(df.groupby(["date", "hour"]).size().rename("trips"))
                communities.append(df.dropna(subset=["community_id"]).groupby(["date", "community_id"]).size().rename("trips"))
                first = False
        counts["file"] = source.name
        counts["mode"] = mode
        counts["seconds"] = round(time.monotonic() - start, 2)
        quality.append(dict(counts))
        print(json.dumps(dict(counts), ensure_ascii=False), flush=True)
    if mode == "taxi":
        months = range(1, 13) if full_year else sorted({int(r["file"][10:12]) for r in quality})
        for month in months:
            prefix = f"taxi_2024-{month:02d}-"
            actual = sum(r["raw_rows"] for r in quality if r["file"].startswith(prefix))
            meta = ROOT / "data/metadata" / f"taxi_count_2024-{month:02d}.json"
            expected = int(json.loads(meta.read_bytes())[0]["n"])
            if actual != expected:
                raise ValueError(f"Taxi source reconciliation failed for month {month}: {actual} != {expected}")
    raw_sample = pd.concat(raw_samples, ignore_index=True)
    cleaned_sample = pd.concat(cleaned_samples, ignore_index=True)
    if mode == "divvy":
        raw_sample.to_csv(SAMPLE / "raw_divvy.csv", index=False)
    else:
        (SAMPLE / "raw_taxi.json").write_text(raw_sample.to_json(orient="records", indent=2), encoding="utf-8")
    cleaned_sample.to_csv(SAMPLE / f"cleaned_{mode}.csv", index=False)
    dump({"method": "5 source rows per processing chunk before filtering, matching retained rows after cleaning",
          "random_seed": 42, "raw_sample_rows": len(raw_sample), "cleaned_sample_rows": len(cleaned_sample),
          "source_files": sorted(raw_sample["_source_file"].unique().tolist()),
          "purpose": "Schema and processing examples across available source files; not an unbiased statistical sample",
          "added_provenance_field": "_source_file"}, SAMPLE / f"sampling_{mode}.json")
    daily = pd.concat(sums).groupby(level=0).sum().reindex(dates, fill_value=0)
    if (daily.trips == 0).any():
        raise ValueError(f"{mode}: missing entire observation day")
    daily["mean_duration_min"] = daily.duration_sum / daily.trips / 60
    daily["mean_miles"] = daily.miles_sum / daily.miles_n.replace(0, np.nan)
    daily["mean_fare_usd"] = daily.fare_sum / daily.fare_n.replace(0, np.nan)
    daily.index.name = "date"
    daily.to_csv(CLEAN / f"{mode}_daily.csv")
    hourly = pd.concat(hours).groupby(level=[0, 1]).sum()
    hourly = hourly.reindex(pd.MultiIndex.from_product([dates, range(24)], names=["date", "hour"]), fill_value=0)
    spatial = pd.concat(communities).groupby(level=[0, 1]).sum()
    spatial = spatial.reindex(pd.MultiIndex.from_product([dates, sorted(areas.ids)], names=["date", "community_id"]), fill_value=0)
    daily = daily[["trips", "mean_duration_min", "mean_miles", "mean_fare_usd"]].add_prefix(mode + "_").reset_index()
    return daily, hourly.rename(mode + "_trips").reset_index(), spatial.rename(mode + "_trips").reset_index(), quality


def main():
    for d in [CLEAN, OUT, SAMPLE]:
        d.mkdir(parents=True, exist_ok=True)
    areas = AreaLookup()
    holidays = parse_holidays()
    wd = weather()
    all_quality, daily, hourly, spatial = [], [], [], []
    for mode in ["divvy", "taxi"]:
        d, h, s, q = clean_and_aggregate(mode, areas)
        daily.append(d); hourly.append(h); spatial.append(s); all_quality.extend(q)
    integrated = daily[0].merge(daily[1], on="date", validate="one_to_one").merge(wd, on="date", validate="one_to_one")
    holidays["date"] = pd.to_datetime(holidays.date)
    integrated = integrated.merge(holidays, on="date", how="left", validate="one_to_one")
    integrated["is_holiday"] = integrated.holiday_name.notna()
    integrated["dow"] = integrated.date.dt.dayofweek
    integrated["month"] = integrated.date.dt.month
    integrated["day_type"] = np.select([integrated.is_holiday, integrated.dow.ge(5)], ["Federal holiday", "Weekend"], default="Weekday")
    integrated.to_csv(OUT / "daily.csv", index=False)
    hr = hourly[0].merge(hourly[1], on=["date", "hour"], validate="one_to_one")
    hr = hr.merge(integrated[["date", "day_type", "is_holiday", "rain_day"]], on="date", validate="many_to_one")
    hr.to_csv(OUT / "hourly.csv", index=False)
    sp = spatial[0].merge(spatial[1], on=["date", "community_id"], validate="one_to_one")
    sp["community_name"] = sp.community_id.map(areas.names)
    sp = sp.merge(integrated[["date", "rain_day", "precip_mm", "tavg_c", "day_type", "month", "dow"]], on="date", validate="many_to_one")
    sp.to_csv(OUT / "community_daily.csv", index=False)
    dump(all_quality, ROOT / "docs/cleaning_quality.json")
    # Independent aggregate reconciliation catches row multiplication and lost joins.
    checks = {"daily_rows": len(integrated), "hourly_rows": len(hr), "community_daily_rows": len(sp),
              "unique_dates": int(integrated.date.nunique()), "calendar_holidays": int(integrated.is_holiday.sum()),
              "community_count": int(sp.community_id.nunique())}
    for mode in ["divvy", "taxi"]:
        col = mode + "_trips"
        clean = sum(q["cleaned_rows"] for q in all_quality if q["mode"] == mode)
        unmatched = sum(q["unmatched_community_rows"] for q in all_quality if q["mode"] == mode)
        if clean != int(integrated[col].sum()) or clean != int(hr[col].sum()) or clean - unmatched != int(sp[col].sum()):
            raise ValueError(f"{mode}: aggregate reconciliation failed")
        checks[mode + "_cleaned_rows"] = clean
        checks[mode + "_spatial_match_rate"] = (clean - unmatched) / clean
    if len(integrated) != 366 or checks["calendar_holidays"] != 11 or len(sp) != 366 * 77:
        raise ValueError("Incomplete integrated dimensions")
    dump(checks, ROOT / "docs/integration_checks.json")
    print(json.dumps(checks, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
