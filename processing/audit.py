"""Produce source checksums and enforce assignment-scale/data-reconciliation gates."""
from pathlib import Path
import hashlib
import json
import csv
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def checksum(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main():
    rows = []
    for path in sorted((ROOT / "data/raw").rglob("*")):
        if not path.is_file() or path.name.endswith(".partial"):
            continue
        source = path.relative_to(ROOT / "data/raw").parts[0]
        rows.append({"source": source, "path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
                     "sha256": checksum(path), "included_in_scale": source in ["divvy", "taxi"]})
    with (ROOT / "docs/file_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "path", "bytes", "sha256", "included_in_scale"])
        writer.writeheader(); writer.writerows(rows)
    original_sizes = {s: sum(r["bytes"] for r in rows if r["source"] == s) for s in ["divvy", "taxi"]}
    profile_path = ROOT / "docs/divvy_source_profile.json"
    profile = json.loads(profile_path.read_text()) if profile_path.exists() else {}
    expected = {Path(r["path"]).name: r["sha256"] for r in rows if r["source"] == "divvy"}
    if ("eligible_record_bytes" not in profile or
            {f["file"]: f.get("sha256") for f in profile.get("files", [])} != expected):
        subprocess.run([sys.executable, str(ROOT / "processing/profile_divvy.py")], check=True)
        profile = json.loads(profile_path.read_text())
    sizes = {"divvy": profile["eligible_record_bytes"], "taxi": original_sizes["taxi"]}
    quality = json.loads((ROOT / "docs/cleaning_quality.json").read_text())
    taxi_exclusions = sum(q.get(k, 0) for q in quality if q["mode"] == "taxi"
                          for k in ["removed_missing_id_or_start", "removed_outside_year", "removed_duplicate_id"])
    scope_count_matches = (sum(q.get("removed_non_bicycle", 0) for q in quality if q["mode"] == "divvy")
                           == profile["excluded_scope_rows"].get("non_bicycle", 0))
    counts = {s: sum(r["source"] == s for r in rows) for s in sizes}
    total = sum(sizes.values())
    audit = {"counting_rule": "Exact original CSV record bytes of unique 2024 bicycles plus original Taxi JSON day archives; no scooters, archives, page caches or derived files",
             "source_original_file_bytes": original_sizes,
             "source_bytes": sizes, "source_files": counts, "total_bytes": total,
             "total_decimal_GB": total / 1e9, "total_binary_GiB": total / 1024 ** 3,
             "max_source_fraction": max(sizes.values()) / total if total else 1,
             "independent_source_families_conservative": 4,
             "source_forms": ["operational CSV files", "public JSON API", "official calendar webpage", "geospatial GeoJSON"],
             "checks": {"all_12_months": counts.get("divvy") == 12 and counts.get("taxi") == 366,
                        "taxi_raw_ids_and_start_dates_valid": taxi_exclusions == 0,
                        "bicycle_scope_matches_cleaning": scope_count_matches,
                        "total_at_least_2GB": total >= 2e9,
                        "total_at_least_2GiB": total >= 2 * 1024 ** 3,
                        "main_sources_at_least_200MB": all(v >= 200e6 for v in sizes.values()),
                        "single_source_at_most_80percent": (max(sizes.values()) <= total * .8) if total else False}}
    audit["all_scale_checks_pass"] = all(audit["checks"].values())
    (ROOT / "docs/scale_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    raw_counts = {s: sum(q["raw_rows"] for q in quality if q["mode"] == s) for s in sizes}
    logs = [json.loads(line) for line in (ROOT / "docs/collection_log.jsonl").read_text().splitlines() if line]
    weather_rows = len(json.loads((ROOT / "data/raw/weather/noaa_2024.json").read_text()))
    area_rows = len(json.loads((ROOT / "data/raw/boundaries/community_areas.geojson").read_text())["features"])
    with (ROOT / "data/cleaned/holidays_2024.csv").open() as f:
        holiday_rows = sum(1 for _ in csv.DictReader(f))
    source_labels = [("divvy", "Divvy / Lyft", "全年原始骑行明细", raw_counts["divvy"], "divvy"),
                     ("taxi", "芝加哥市", "全年原始出租车明细", raw_counts["taxi"], "chicago_taxi"),
                     ("weather", "NOAA NCEI", "两个天气站的站日观测", weather_rows, "noaa"),
                     ("holidays", "美国 OPM", "2024 联邦节假日", holiday_rows, "opm"),
                     ("boundaries", "芝加哥市", "社区多边形", area_rows, "chicago_boundaries")]
    section = ["## 本次运行的实际采集统计", "", "下表保留完整原文件大小；规模门槛采用剔除范围外和重复记录后的有效字节，二者分开列报于 scale_audit.json。", "", "| 数据目录 | 发布者 | 记录口径 | 原始记录数 | 完整原文件字节 | 采集时间范围 美国洛杉矶当地时间 |",
               "|---|---|---|---:|---:|---|"]
    for directory, publisher, description, n, logsource in source_labels:
        b = sum(r["bytes"] for r in rows if r["source"] == directory)
        times = [datetime.fromisoformat(r["collected_at_utc"]).astimezone(ZoneInfo("America/Los_Angeles"))
                 for r in logs if r.get("source") == logsource and r.get("status") in ["downloaded", "extracted", "assembled"]]
        span = (min(times).strftime("%Y-%m-%d %H:%M") + " 至 " + max(times).strftime("%Y-%m-%d %H:%M")) if times else "见采集日志"
        section.append(f"| {directory} | {publisher} | {description} | {n:,} | {b:,} | {span} |")
    section += ["", f"两个主要源有效明细合计 {total:,} 字节（{total/1e9:.3f} GB），最大单源占比 {audit['max_source_fraction']:.2%}。辅助源不计入总体规模门槛。", ""]
    source_doc = ROOT / "data_sources.md"
    marker = "<!-- RUN_STATISTICS -->"
    original = source_doc.read_text(encoding="utf-8").split(marker)[0].rstrip()
    source_doc.write_text(original + "\n\n" + marker + "\n" + "\n".join(section), encoding="utf-8")
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    if not audit["all_scale_checks_pass"]:
        raise SystemExit("Scale checks failed; do not present the project as meeting assignment thresholds")


if __name__ == "__main__":
    main()
