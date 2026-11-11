"""Measure exact original CSV record bytes for the bicycle study cohort."""
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIKES = {"classic_bike", "electric_bike"}


class ByteLines:
    def __init__(self, stream):
        self.stream = stream
        self.bytes = 0
        self.digest = hashlib.sha256()

    def __iter__(self):
        return self

    def __next__(self):
        data = next(self.stream)
        first = self.bytes == 0
        self.bytes += len(data)
        self.digest.update(data)
        return data.decode("utf-8-sig" if first else "utf-8")


def profile():
    paths = sorted((ROOT / "data/raw/divvy").glob("*.csv"))
    if len(paths) != 12:
        raise ValueError("Need all 12 Divvy source files")
    seen, files = set(), []
    types, excluded = Counter(), Counter()
    for path in paths:
        n, eligible, eligible_bytes = 0, 0, 0
        with path.open("rb") as stream:
            lines = ByteLines(stream)
            reader = csv.reader(lines)
            fields = next(reader)
            id_i, time_i, type_i = [fields.index(k) for k in ["ride_id", "started_at", "rideable_type"]]
            previous = lines.bytes
            for row in reader:
                record_bytes = lines.bytes - previous
                previous = lines.bytes
                n += 1
                kind = row[type_i]
                types[kind] += 1
                try:
                    started = datetime.fromisoformat(row[time_i])
                except ValueError:
                    started = None
                if not row[id_i] or started is None:
                    excluded["missing_id_or_invalid_start"] += 1
                elif started.year != 2024:
                    excluded["outside_year"] += 1
                elif kind not in BIKES:
                    excluded["non_bicycle"] += 1
                elif row[id_i] in seen:
                    excluded["duplicate_id"] += 1
                else:
                    seen.add(row[id_i])
                    eligible += 1
                    eligible_bytes += record_bytes
        files.append({"file": path.name, "rows": n, "bytes": path.stat().st_size,
                      "sha256": lines.digest.hexdigest(), "eligible_rows": eligible,
                      "eligible_record_bytes": eligible_bytes})
    result = {"files": files, "type_counts": dict(types), "excluded_scope_rows": dict(excluded),
              "total_rows": sum(f["rows"] for f in files), "total_bytes": sum(f["bytes"] for f in files),
              "eligible_rows": sum(f["eligible_rows"] for f in files),
              "eligible_record_bytes": sum(f["eligible_record_bytes"] for f in files),
              "scope": {"year": 2024, "rideable_types": sorted(BIKES), "dedup": "first ID in source-file order"},
              "byte_rule": "Exact original UTF-8 record bytes consumed by CSV reader; excludes headers, non-bicycles, invalid/out-of-year start and repeated IDs"}
    if result["eligible_rows"] + sum(excluded.values()) != result["total_rows"]:
        raise ValueError("Cohort row accounting mismatch")
    (ROOT / "docs/divvy_source_profile.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    profile()
