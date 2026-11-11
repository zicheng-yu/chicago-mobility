# 数据来源与关联说明

研究范围为 2024 年 1 月 1 日至 12 月 31 日的芝加哥。采集发生于 2026 年 11 月 10 日（美国洛杉矶当地日期），精确 UTC 时间记录于 `docs/collection_log.jsonl`。实际文件规模、行数及校验值由运行生成，不把估计写成实测。

| 数据 | 发布者与独立性 | 获取方法与主要字段 | 跨源关联 | 角色 |
|---|---|---|---|---|
| Divvy 月度骑行 | Divvy / Lyft，独立运营记录 | 官方月度 ZIP 内 CSV。ride_id、started_at、ended_at、start_lat、start_lng、member_casual | 当地日期；起点空间匹配社区 | 主要源 |
| Taxi Trips 2024 | 芝加哥市，监管报送记录 | Socrata JSON API。trip_id、trip_start_timestamp、trip_end_timestamp、trip_seconds、trip_miles、pickup_community_area、dropoff_community_area、fare、trip_total、payment_type | 当地日期；官方社区编号 | 主要源 |
| GHCN 日天气 | 美国 NOAA NCEI，独立地面观测 | 日汇总 API，metric 单位，保留质量属性。DATE、STATION、PRCP、TMAX、TMIN、SNOW、AWND | DATE 与出行当地日期关联 | 辅助源 |
| 联邦节假日 | 美国 OPM，独立官方日历 | 保存官方网页并解析 2024 表，日期、名称 | 日期关联 | 辅助源 |
| 77 个社区边界 | 芝加哥市，地理辅助数据 | 官方 GeoJSON，area_numbe、community、geometry | 出租车社区编号映射；单车点落区 | 辅助源 |

按底层记录的形成过程识别四类独立信源：共享单车运营、出租车监管报送、NOAA 气象观测和 OPM 官方日历；社区边界作为地理辅助源。Divvy 由 Lyft 运营发布，数据所有权归芝加哥市，其骑行记录与出租车报送记录属于独立系统，不是同一底层数据的镜像。数据形态覆盖原始运营 CSV、公开 API、官方网页和地理空间数据。

## 官方入口

- [Divvy 数据说明与下载入口](https://divvybikes.com/system-data)
- [Divvy 官方存储桶](https://divvy-tripdata.s3.amazonaws.com/index.html)
- [Divvy 数据许可](https://divvybikes.com/data-license-agreement)
- [芝加哥出租车数据](https://data.cityofchicago.org/Transportation/Taxi-Trips-2024-/ajtu-isnz)
- [出租车字段元数据](https://data.cityofchicago.org/api/views/ajtu-isnz.json)
- [芝加哥社区边界](https://data.cityofchicago.org/Facilities-Geographic-Boundaries/Boundaries-Community-Areas/igwz-8jzy)
- [NOAA 日汇总数据说明](https://www.ncei.noaa.gov/access/search/data-search/daily-summaries/)
- [NOAA API 文档](https://www.ncei.noaa.gov/access/search/documentation/data-service/)
- [NOAA GHCND 字段与单位说明](https://www.ncei.noaa.gov/pub/data/cdo/documentation/GHCND_documentation.pdf)
- [OPM 联邦节假日](https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/)
- [Socrata 访问限流说明](https://dev.socrata.com/docs/app-tokens)

## 天气站与覆盖范围

USW00094846 为芝加哥奥黑尔机场站，USW00014819 为中途机场站。保留每个站的每日观测与属性；报告使用两站有效值均值，属于市级天气代理，不能反映每个社区的局部降水。PRCP 的液态当量口径不能直接解释为纯降雨量。

## 许可和采集边界

Divvy 数据依照官方数据许可用于非商业课程分析，原始许可网页快照只在本机留存，提交材料保留网址与校验记录。其许可对一般分析和数据挖掘的表述有所区分，因此本项目的 KMeans 步骤只使用出租车与 NOAA 天气，单车用于常规统计比较。少量样本作为本研究的来源说明，不另行发布为独立数据集。芝加哥数据集的元数据标注为 See Terms of Use，应遵守官方门户使用条款并注明来源。NOAA 和 OPM 的政府公开材料用于课程研究并保留来源。

采集无需登录或账号令牌，不绕过验证码、付费墙、认证和访问控制。只请求研究年份。下载脚本记录失败并退避重试；遇到 429 限流时应尊重 Retry-After。没有采集乘客身份、账号或联系方式，也没有请求出租车持续性车辆标识。

## 字节数与记录数

运行 `python processing/audit.py` 生成 `docs/file_manifest.csv` 和 `docs/scale_audit.json`。清单保留完整原 CSV 文件大小；有效规模则用 `processing/profile_divvy.py` 按 CSV 解析器实际消耗的 UTF-8 字节，逐记录扣除滑板车、无效年份、缺少 ID 和重复 ID，连表头也不计入。出租车使用解码后的 JSON 对象内容，分页时仅合并响应数组为日归档，不改动字段和值；原始 ID 与日期检查须通过。日归档与页面缓存不重复计量。JSON 的字段名开销包含在内，ZIP 大小另见采集日志；未提供压缩 Content-Length 的 API 响应不宣称已测得线缆传输字节。两个主要源均使用全年真实记录，不复制或填充内容凑量。

<!-- RUN_STATISTICS -->
## 本次运行的实际采集统计

下表保留完整原文件大小；规模门槛采用剔除范围外和重复记录后的有效字节，二者分开列报于 scale_audit.json。

| 数据目录 | 发布者 | 记录口径 | 原始记录数 | 完整原文件字节 | 采集时间范围 美国洛杉矶当地时间 |
|---|---|---|---:|---:|---|
| divvy | Divvy / Lyft | 全年原始骑行明细 | 5,860,568 | 1,189,139,393 | 2026-11-10 18:26 至 2026-11-10 20:07 |
| taxi | 芝加哥市 | 全年原始出租车明细 | 6,480,350 | 1,986,872,838 | 2026-11-10 18:35 至 2026-11-10 20:35 |
| weather | NOAA NCEI | 两个天气站的站日观测 | 732 | 194,547 | 2026-11-10 18:25 至 2026-11-10 18:25 |
| holidays | 美国 OPM | 2024 联邦节假日 | 11 | 151,930 | 2026-11-10 18:25 至 2026-11-10 18:25 |
| boundaries | 芝加哥市 | 社区多边形 | 77 | 2,072,102 | 2026-11-10 18:25 至 2026-11-10 18:25 |

两个主要源有效明细合计 3,149,961,547 字节（3.150 GB），最大单源占比 63.08%。辅助源不计入总体规模门槛。
