"""Run the project stages sequentially; optionally wait for current collection jobs."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent


def ready():
    raw=ROOT/'data/raw'
    return (len(list((raw/'divvy').glob('*.csv')))==12
            and len(list((raw/'taxi').glob('taxi_2024-??-??.json')))==366
            and len(list((ROOT/'data/metadata').glob('taxi_count_2024-??.json')))==12
            and all((raw/p).is_file() for p in ['weather/noaa_2024.json','holidays/opm_holidays.html','boundaries/community_areas.geojson']))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--wait-for-downloads',action='store_true')
    parser.add_argument('--skip-collection',action='store_true')
    args=parser.parse_args()
    (ROOT/'build').mkdir(exist_ok=True)
    status_file=ROOT/'build/pipeline_status.json'
    def status(stage,**extra):
        d={'stage':stage,'updated_at_utc':datetime.now(timezone.utc).isoformat(),**extra}
        status_file.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(d,ensure_ascii=False),flush=True)
    if args.wait_for_downloads:
        status('waiting_for_complete_sources')
        while not ready():
            time.sleep(30)
    elif not args.skip_collection:
        status('collecting')
        subprocess.run([sys.executable,'crawler/collect.py','--workers','2'],cwd=ROOT,check=True)
    steps=[('cleaning_and_integration',['processing/build.py']),
           ('analysis',['analysis/analyze.py']),
           ('scale_and_checksum_audit',['processing/audit.py']),
           ('data_lineage',['-m','analysis.lineage']),
           ('word_report',['docs/build_report.py'])]
    with (ROOT/'build/pipeline.log').open('w',encoding='utf-8') as log:
        for stage,cmd in steps:
            status(stage)
            r=subprocess.run([sys.executable,*cmd],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            log.flush()
            if r.returncode:
                status('failed',failed_stage=stage,exit_code=r.returncode)
                raise SystemExit(r.returncode)
    status('analysis_and_report_ready_for_visual_review')


if __name__=='__main__':main()
