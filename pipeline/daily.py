"""Daily pipeline runner.

    python daily.py             full sweep, then board scans, then queue
    python daily.py --quick     board scans and queue only, about 2 minutes
    python daily.py --dry-run   show the steps without running anything

Every step writes its own output file. Failures do not stop the run. The log is
kept in logs/daily_YYYY-MM-DD.log.
"""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
LOGS = HERE / "logs"

FULL = [
    ("job_sweep", ["job_sweep.py"]),
    ("linkedin_sweep", ["linkedin_sweep.py"]),
    ("indeed_sweep", ["indeed_sweep.py"]),
    ("stepstone_sweep", ["stepstone_sweep.py"]),
    ("ba_sweep", ["ba_sweep.py"]),
    ("glassdoor_sweep", ["glassdoor_sweep.py"]),
    ("corporate_sweep", ["corporate_sweep.py"]),
    ("fintech_sweep", ["fintech_sweep.py"]),
    ("yc_sweep", ["yc_sweep.py"]),
]
QUICK = [
    ("emea_ashby_scan", ["emea_ashby_scan.py"]),
    ("lever_scan", ["lever_scan.py"]),
    ("remote_first_scan", ["remote_first_scan.py"]),
    ("remote_first_scan_gh", ["remote_first_scan_gh.py"]),
]
TAIL = [
    ("scored_queue", ["scored_queue.py"]),
]


def run(name, argv, log):
    started = datetime.now()
    print(f"[{started:%H:%M:%S}] {name} ...", flush=True)
    log.write(f"\n===== {name} {started:%Y-%m-%d %H:%M:%S} =====\n")
    log.flush()
    try:
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", *argv],
            cwd=HERE,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        log.write(out)
        log.flush()
        tail = [l for l in out.strip().splitlines() if l.strip()][-3:]
        for line in tail:
            print("    " + line[:150])
        if proc.returncode != 0:
            print(f"    exited {proc.returncode}, continuing")
        return proc.returncode == 0
    except subprocess.TimeoutExpired:
        log.write("TIMEOUT\n")
        print("    timed out, continuing")
        return False
    except Exception as exc:
        log.write(f"ERROR {exc}\n")
        print(f"    error {exc}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="skip the slow board scrapers")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    steps = (QUICK if args.quick else FULL) + (QUICK if not args.quick else []) + TAIL
    if args.dry_run:
        for name, argv in steps:
            print(f"{name}: python {' '.join(argv)}")
        return

    LOGS.mkdir(exist_ok=True)
    log_path = LOGS / f"daily_{datetime.now():%Y-%m-%d}.log"
    ok = 0
    with log_path.open("a", encoding="utf-8") as log:
        for name, argv in steps:
            if run(name, argv, log):
                ok += 1
    print(f"\n{ok}/{len(steps)} steps clean. Log: {log_path}")
    print("Next: python status.py")


if __name__ == "__main__":
    main()
