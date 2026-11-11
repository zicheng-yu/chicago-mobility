"""Simple descriptive comparisons, calendar-adjusted associations and KMeans."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
FIG = OUT / "figures"
BLUE = "#17678A"
ORANGE = "#CB7435"
COLORS = {"divvy": BLUE, "taxi": ORANGE}
LABELS = {"divvy": "共享单车", "taxi": "出租车"}


def configure():
    candidates = ["/System/Library/Fonts/STHeiti Light.ttc", "/System/Library/Fonts/Supplemental/Songti.ttc",
                  "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
    for path in candidates:
        if Path(path).exists():
            fontManager.addfont(path)
            plt.rcParams["font.family"] = FontProperties(fname=path).get_name()
            break
    plt.rcParams.update({"axes.unicode_minus": False, "font.size": 11, "axes.titlesize": 16,
                         "axes.labelsize": 11, "figure.facecolor": "white", "axes.spines.top": False,
                         "axes.spines.right": False, "savefig.dpi": 180})


def dump(obj, path):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def save(fig, name, source="来源 Divvy、芝加哥市出租车记录、NOAA，2024 年，芝加哥当地日期"):
    fig.text(.5, .015, source, ha="center", va="bottom", fontsize=9, color="#555555")
    fig.savefig(FIG / (name + ".png"), bbox_inches="tight", pad_inches=.16)
    fig.savefig(FIG / (name + ".pdf"), bbox_inches="tight", pad_inches=.16)
    plt.close(fig)


def design(df):
    continuous = pd.DataFrame({"precip_10mm": df.precip_mm / 10, "temp_10c": df.tavg_c / 10,
                               "temp_squared": (df.tavg_c / 10) ** 2,
                               "wind_mps": df.wind_mps, "holiday": df.is_holiday.astype(int)}, index=df.index)
    calendar = pd.get_dummies(df[["month", "dow"]].astype(str), drop_first=True, dtype=float)
    X = pd.concat([pd.Series(1., index=df.index, name="intercept"), continuous, calendar], axis=1)
    return X.astype(float)


def fit_hac(X, y, lag=7):
    """OLS with Newey-West covariance and Bartlett weights, lag 7 days."""
    a = np.asarray(X, float)
    y = np.asarray(y, float)
    n, p = a.shape
    if n <= p or np.linalg.matrix_rank(a) != p:
        raise ValueError("Regression design is rank deficient")
    beta = np.linalg.lstsq(a, y, rcond=None)[0]
    resid = y - a @ beta
    bread = np.linalg.inv(a.T @ a)
    scores = a * resid[:, None]
    meat = scores.T @ scores
    for k in range(1, lag + 1):
        cross = scores[k:].T @ scores[:-k]
        meat += (1 - k / (lag + 1)) * (cross + cross.T)
    covariance = bread @ meat @ bread * n / (n - p)
    se = np.sqrt(np.maximum(np.diag(covariance), 0))
    return beta, se, float(1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean())))


def main():
    configure()
    FIG.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(ROOT / "data/integrated/daily.csv", parse_dates=["date"])
    hourly = pd.read_csv(ROOT / "data/integrated/hourly.csv", parse_dates=["date"])
    spatial = pd.read_csv(ROOT / "data/integrated/community_daily.csv", parse_dates=["date"])
    quality = json.loads((ROOT / "docs/cleaning_quality.json").read_text())
    checks = json.loads((ROOT / "docs/integration_checks.json").read_text())
    df["is_holiday"] = df.is_holiday.astype(str).str.lower().eq("true")
    df["rain_day"] = df.rain_day.astype(str).str.lower().eq("true")
    spatial["rain_day"] = spatial.rain_day.astype(str).str.lower().eq("true")
    summary = {"period": ["2024-01-01", "2024-12-31"], "days": len(df), "counts": {},
               "rain_days": int(df.rain_day.sum()), "holiday_days": int(df.is_holiday.sum()),
               "spatial_match_rates": {k: checks[k + "_spatial_match_rate"] for k in LABELS}}
    for mode in LABELS:
        q = [r for r in quality if r["mode"] == mode]
        raw = sum(r["raw_rows"] for r in q)
        cleaned = sum(r["cleaned_rows"] for r in q)
        summary["counts"][mode] = {"raw": raw, "cleaned": cleaned, "retained_pct": 100 * cleaned / raw,
                                   "daily_min": int(df[mode + "_trips"].min()),
                                   "daily_max": int(df[mode + "_trips"].max()),
                                   "daily_mean": float(df[mode + "_trips"].mean())}

    # 1 Overall time pattern, same unit for both modes.
    monthly = df.groupby("month")[["divvy_trips", "taxi_trips", "tavg_c", "precip_mm"]].mean()
    monthly.to_csv(OUT / "monthly.csv")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for mode in LABELS:
        ax.plot(monthly.index, monthly[mode + "_trips"] / 1000, marker="o", lw=2, color=COLORS[mode], label=LABELS[mode])
    ax.set(xticks=range(1, 13), xlabel="月份", ylabel="月内平均每日记录量 千次", title="两种出行方式的季节变化是否一致？")
    ax.set_ylim(bottom=0); ax.legend(frameon=False); ax.grid(axis="y", alpha=.2)
    fig.tight_layout(rect=[0, .05, 1, 1]); save(fig, "01_monthly")

    # 2 Unadjusted weather relationship, explicitly distinct from the model below.
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharex=True)
    for ax, mode in zip(axes, LABELS):
        for wet, label, marker, alpha in [(False, "降水量 < 1 mm", "o", .5), (True, "降水量 ≥ 1 mm", "x", .8)]:
            sub = df[df.rain_day == wet]
            ax.scatter(sub.tavg_c, sub[mode + "_trips"] / 1000, s=25, marker=marker, color=COLORS[mode], alpha=alpha, label=label)
        ax.set(title=LABELS[mode], xlabel="两站日最高与最低温度均值 ℃", ylabel="每日记录量 千次")
        ax.legend(frameon=False, fontsize=9); ax.grid(alpha=.15)
    fig.suptitle("不同温度和降水条件下 出行记录量如何变化？", fontsize=16)
    fig.tight_layout(rect=[0, .06, 1, .94]); save(fig, "02_weather_scatter")

    # 3 Calendar-controlled associations. No forecasting or causal claim.
    model_df = df.dropna(subset=["precip_mm", "tavg_c", "wind_mps"]).copy()
    X = design(model_df)
    models = []
    for mode in LABELS:
        beta, se, r2 = fit_hac(X, np.log1p(model_df[mode + "_trips"]))
        for i, name in enumerate(X.columns):
            models.append({"mode": mode, "term": name, "coef": float(beta[i]), "se_hac7": float(se[i]),
                           "percent": float(np.expm1(beta[i]) * 100),
                           "low_percent": float(np.expm1(beta[i] - 1.96 * se[i]) * 100),
                           "high_percent": float(np.expm1(beta[i] + 1.96 * se[i]) * 100), "r2": r2, "n": len(model_df)})
    model = pd.DataFrame(models)
    model.to_csv(OUT / "model_coefficients.csv", index=False)
    summary["models"] = {m: {t: model[(model["mode"] == m) & (model.term == t)].iloc[0].to_dict()
                                 for t in ["precip_10mm", "holiday"]} for m in LABELS}
    summary["model_rows"] = len(model_df)
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.5))
    for ax, term, title in zip(axes, ["precip_10mm", "holiday"], ["日降水量增加 10 mm", "联邦节假日与非节假日"]):
        for i, mode in enumerate(LABELS):
            row = model[(model["mode"] == mode) & (model.term == term)].iloc[0]
            ax.errorbar(row.percent, i, xerr=[[row.percent-row.low_percent], [row.high_percent-row.percent]],
                        fmt="o", color=COLORS[mode], capsize=5, markersize=8)
            ax.annotate(f"{row.percent:+.1f}%", (row.percent, i), xytext=(0, 12), textcoords="offset points", ha="center")
        ax.axvline(0, color="#777777", lw=1)
        ax.set(yticks=[0, 1], yticklabels=list(LABELS.values()), ylim=(-.6, 1.65), xlabel="记录量关联变化 %", title=title)
        ax.grid(axis="x", alpha=.2)
    fig.suptitle("控制月份 星期与温度后 关联方向是否相同？", fontsize=16)
    fig.text(.5, .065, "线段为 HAC 7 日协方差的近似 95% 区间，回归因变量为 log(1+日记录量)", ha="center", fontsize=9)
    fig.tight_layout(rect=[0, .10, 1, .93]); save(fig, "03_adjusted_associations", "来源 Divvy、芝加哥市、NOAA、OPM，2024 年。观察性关联，不作因果解释")

    # 4 Holiday/workday hour profiles, each group divided by its number of days.
    day_counts = df.day_type.value_counts()
    profile = hourly.groupby(["day_type", "hour"])[["divvy_trips", "taxi_trips"]].sum().astype(float)
    for group in day_counts.index:
        profile.loc[group] = profile.loc[group].to_numpy() / day_counts[group]
    profile.to_csv(OUT / "hour_profiles.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharex=True)
    for ax, mode in zip(axes, LABELS):
        for day_type, cn, style in [("Weekday", "普通工作日", "-"), ("Weekend", "周末", "--"), ("Federal holiday", "联邦节假日", ":")]:
            sub = profile.loc[day_type]
            ax.plot(sub.index, sub[mode + "_trips"], label=f"{cn} {day_counts[day_type]} 天", linestyle=style, lw=2)
        ax.set(title=LABELS[mode], xlabel="当地小时", ylabel="每类日期平均每小时记录量 次", xticks=[0, 6, 12, 18, 23])
        ax.set_ylim(bottom=0); ax.legend(frameon=False, fontsize=9); ax.grid(alpha=.15)
    fig.suptitle("节假日的出行时段与普通工作日有何不同？", fontsize=16)
    fig.tight_layout(rect=[0, .06, 1, .94]); save(fig, "04_daytype_hours", "来源 Divvy、芝加哥市、OPM，2024 年。出租车时间取整至 15 分钟，节假日仅 11 天")

    # 5 Spatial relation: keep native geographic boundaries, use identical log scale.
    geo = json.loads((ROOT / "data/raw/boundaries/community_areas.geojson").read_text())
    area_totals = spatial.groupby(["community_id", "community_name"])[["divvy_trips", "taxi_trips"]].sum().reset_index()
    area_totals.to_csv(OUT / "community_totals.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(9, 6.7))
    vmax = np.log10(1 + area_totals[["divvy_trips", "taxi_trips"]].max().max())
    for ax, mode in zip(axes, LABELS):
        patches, values = [], []
        totals = area_totals.set_index("community_id")[mode + "_trips"]
        for feature in geo["features"]:
            cid = int(feature["properties"]["area_numbe"])
            polys = feature["geometry"]["coordinates"] if feature["geometry"]["type"] == "MultiPolygon" else [feature["geometry"]["coordinates"]]
            for polygon in polys:
                patches.append(Polygon(polygon[0]))
                values.append(np.log10(1 + totals.get(cid, 0)))
        collection = PatchCollection(patches, cmap="Blues", edgecolor="white", linewidth=.3, clim=(0, vmax))
        collection.set_array(np.array(values)); ax.add_collection(collection); ax.autoscale_view()
        ax.set_aspect(1 / np.cos(np.radians(41.9))); ax.set_axis_off(); ax.set_title(LABELS[mode])
    fig.colorbar(collection, ax=axes, fraction=.035, pad=.025, label="全年社区起点记录量 log10(1+次数)")
    fig.suptitle("两种出行方式集中在相同的社区吗？", fontsize=16)
    fig.subplots_adjust(top=.90, bottom=.07, left=.02, right=.86, wspace=.08)
    save(fig, "05_community_maps", "来源 Divvy 起点坐标、出租车上车社区、芝加哥市社区边界，2024 年。仅含成功匹配社区的记录")

    # 6 Month/weekday-normalized precipitation comparisons within communities.
    normalized = spatial.copy()
    for mode in LABELS:
        col = mode + "_trips"
        baseline = normalized.groupby(["community_id", "month", "dow"])[col].transform("mean")
        normalized[mode + "_index"] = normalized[col] / baseline.replace(0, np.nan)
    contrasts = []
    for cid, sub in normalized.groupby("community_id"):
        row = {"community_id": int(cid), "community_name": sub.community_name.iloc[0]}
        for mode in LABELS:
            col = mode + "_index"
            wet = sub.loc[sub.rain_day, col].mean()
            dry = sub.loc[~sub.rain_day, col].mean()
            row[mode + "_wet_dry_pct"] = (wet / dry - 1) * 100 if dry > 0 else np.nan
            row[mode + "_annual"] = int(sub[mode + "_trips"].sum())
        contrasts.append(row)
    contrasts = pd.DataFrame(contrasts)
    contrasts.to_csv(OUT / "community_precip_comparison.csv", index=False)
    comparable = contrasts[(contrasts.divvy_annual >= 10000) & (contrasts.taxi_annual >= 10000)].dropna()
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.scatter(comparable.divvy_wet_dry_pct, comparable.taxi_wet_dry_pct, s=45, color=BLUE, alpha=.75)
    for _, row in comparable.nlargest(4, "divvy_annual").iterrows():
        ax.annotate(row.community_name.title(), (row.divvy_wet_dry_pct, row.taxi_wet_dry_pct), xytext=(5, 5), textcoords="offset points", fontsize=8)
    ax.axhline(0, color="#777777", lw=.8); ax.axvline(0, color="#777777", lw=.8)
    ax.set(xlabel="共享单车 降水日相对非降水日变化 %", ylabel="出租车 降水日相对非降水日变化 %",
           title=f"同一社区内 两种方式的降水日变化是否一致？\n{len(comparable)} 个社区，两种方式全年均至少 1 万次记录")
    ax.grid(alpha=.15)
    fig.tight_layout(rect=[0, .08, 1, 1]); save(fig, "06_community_precip", "来源 Divvy、芝加哥市、NOAA，2024 年。先按社区 月份 星期的均值标准化，温度等差异仍可能存在")
    summary["spatial_comparable_communities"] = len(comparable)
    summary["community_precip_counts"] = {
        "compared": len(comparable),
        "bicycle_lower": int(comparable.divvy_wet_dry_pct.lt(0).sum()),
        "taxi_lower": int(comparable.taxi_wet_dry_pct.lt(0).sum()),
        "taxi_higher": int(comparable.taxi_wet_dry_pct.gt(0).sum())}

    # 7 Mining requirement: fixed, interpretable clustering of integrated day features.
    # Divvy is used for ordinary statistical analysis. Keep the mining stage
    # confined to government taxi/weather data under the source-use boundary.
    features = ["taxi_trips", "tavg_c", "precip_mm", "wind_mps"]
    cluster_df = df[["date", *features]].dropna(subset=features).copy()
    scaler = StandardScaler()
    z = scaler.fit_transform(cluster_df[features])
    km = KMeans(n_clusters=3, n_init=20, random_state=42)
    raw_labels = km.fit_predict(z)
    order = sorted(range(3), key=lambda i: cluster_df.loc[raw_labels == i, "tavg_c"].mean())
    names = {i: f"类别 {chr(65 + rank)}" for rank, i in enumerate(order)}
    cluster_df["cluster"] = [names[i] for i in raw_labels]
    cluster_df[["date", "cluster"] + features].to_csv(OUT / "day_clusters.csv", index=False)
    centers = cluster_df.groupby("cluster")[features].mean()
    centers["days"] = cluster_df.groupby("cluster").size()
    centers.to_csv(OUT / "cluster_profiles.csv")
    summary["clustering"] = {"k": 3, "random_state": 42, "n_init": 20, "features": features,
                              "silhouette": float(silhouette_score(z, raw_labels)),
                              "profiles": centers.reset_index().to_dict(orient="records")}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    palette = ["#437F97", "#D18A45", "#62936D"]
    for (label, sub), color in zip(cluster_df.groupby("cluster"), palette):
        axes[0].scatter(sub.tavg_c, sub.taxi_trips / 1000, s=25, alpha=.7, color=color, label=label)
    axes[0].set(xlabel="两站日最高与最低温度均值 ℃", ylabel="出租车每日记录量 千次")
    axes[0].legend(frameon=False)
    heat = centers[features].apply(lambda s: (s - cluster_df[s.name].mean()) / cluster_df[s.name].std(ddof=0))
    color_limit = max(2, float(np.ceil(np.abs(heat.to_numpy()).max())))
    im = axes[1].imshow(heat, cmap="RdBu_r", vmin=-color_limit, vmax=color_limit, aspect="auto")
    axes[1].set(xticks=range(4), xticklabels=["出租车量", "温度", "降水", "风速"], yticks=range(3), yticklabels=centers.index)
    for i in range(3):
        for j in range(4):
            axes[1].text(j, i, f"{heat.iloc[i,j]:.1f}", ha="center", va="center",
                         color="white" if abs(heat.iloc[i,j]) > .6 * color_limit else "black", fontsize=11)
    fig.colorbar(im, ax=axes[1], label="相对全年均值的标准差")
    fig.suptitle("出租车与天气特征 能识别哪些日级模式？", fontsize=16)
    fig.tight_layout(rect=[0, .07, 1, .94]); save(fig, "07_day_clusters", f"来源 芝加哥市、NOAA，2024 年。KMeans k=3，标准化四个特征，轮廓系数 {summary['clustering']['silhouette']:.3f}")

    dump(summary, OUT / "summary.json")
    dump({"summary": summary,
          "monthly": json.loads(monthly.reset_index().to_json(orient="records")),
          "hour_profiles": json.loads(profile.reset_index().to_json(orient="records")),
          "community_totals": json.loads(area_totals.to_json(orient="records")),
          "clusters": summary["clustering"]["profiles"]}, OUT / "deck_data.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
