#!/usr/bin/env python3
r"""
TaskLoop — a zero-dependency scheduled job runner for Windows/macOS/Linux.
Sells as: "automation scripts + scheduling setup" (€20–€45 per Zapier/n8n
gig on PeoplePerHour; no server needed = margin)

Why it sells: 'Zapier setup' gigs (€30–€115) mostly just run something on a
schedule and handle failures. TaskLoop does that with one file, no web
service, no account, no recurring fees — the pitch is 'own your automation'.

What it does:
    - Runs any command on an interval (--every 60 = every 60 seconds)
    - Cron-style scheduling: --cron 'M H dom mon dow' (local time)
    - Writes a structured run log (JSONL): timestamp, duration, exit code,
      last 20 output lines
    - Retries failed jobs with exponential backoff (--retries 3)
    - --startup flag: generates the OS-native autostart setup
      (Task Scheduler XML on Windows, launchd plist on macOS, systemd/crontab
      line on Linux) so the loop survives reboots — printed, never installed
    - Lock file prevents two copies from running the same job

Usage:
    python taskloop.py run "python backup.py" --every 3600
    python taskloop.py run "python scrapekit.py https://x.com --emails --out e.json" --cron "0 9 * * 1-5"
    python taskloop.py startup "python taskloop.py run \"python job.py\" --every 900"
    python taskloop.py log --tail 20            # inspect past runs
    python taskloop.py log --failures          # only failures
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

LOG_FILE = Path("taskloop-log.jsonl")
LOCK_FILE = Path("taskloop.lock")


def log_entry(job: str, exit_code, duration: float, output: str, retry: int):
    entry = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
             "job": job, "exit": exit_code, "duration_s": round(duration, 2),
             "retry": retry, "output_tail": output.splitlines()[-20:]}
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def run_once(job: str, retries: int) -> bool:
    for attempt in range(retries + 1):
        started = time.time()
        try:
            result = subprocess.run(job, shell=True, capture_output=True,
                                   text=True, timeout=3600)
            output = (result.stdout or "") + (result.stderr or "")
            entry = log_entry(job, result.returncode, time.time() - started, output, attempt)
            if result.returncode == 0:
                print(f"[{entry['ts']}] OK ({entry['duration_s']}s) {job}")
                return True
            print(f"[{entry['ts']}] exit {result.returncode} (attempt {attempt + 1}) {job}")
        except subprocess.TimeoutExpired:
            log_entry(job, -1, time.time() - started, "timeout after 3600s", attempt)
            print(f"[timeout] {job}")
        except Exception as e:
            log_entry(job, -1, time.time() - started, str(e), attempt)
            print(f"[error] {e}")
        if attempt < retries:
            backoff = 2 ** attempt
            print(f"  retrying in {backoff}s...")
            time.sleep(backoff)
    return False


def cron_matches(pattern: str, now: datetime.datetime) -> bool:
    """Minimal 5-field cron: number, *, ranges, lists, */step. Local time."""
    fields = pattern.split()
    if len(fields) != 5:
        sys.exit(f"error: --cron needs 5 fields 'M H dom mon dow', got {pattern!r}")
    ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
    values = [now.minute, now.hour, now.day, now.month, (now.weekday() + 1) % 7]
    for field, spec, current, (lo, hi) in zip(fields, fields, values, ranges):
        if spec == "*":
            continue
        matched = False
        for part in spec.split(","):
            if "/" in part:
                base, _, step = part.partition("/")
                step = int(step)
                start = lo if base == "*" else int(base)
                if start <= current and (current - start) % step == 0:
                    matched = True
            elif "-" in part:
                a, _, b = part.partition("-")
                if int(a) <= current <= int(b):
                    matched = True
            elif int(part) == current:
                matched = True
            if matched:
                break
        if not matched:
            return False
    return True


def cmd_run(args):
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text())
            os.kill(pid, 0)
            sys.exit(f"error: another taskloop (pid {pid}) is running this job — "
                     "delete {LOCK_FILE} if stale")
        except (ValueError, PermissionError, AttributeError):
            pass  # Windows: os.kill(pid,0) semantics differ; fall through
        except Exception:
            pass  # stale lock from a dead process
    LOCK_FILE.write_text(str(os.getpid()))
    try:
        print(f"taskloop: {args.job!r} starting "
              + (f"every {args.every}s" if args.every else f"cron '{args.cron}'")
              + f", retries={args.retries} — Ctrl+C to stop")
        last_minute = None
        while True:
            try:
                if args.every:
                    run_once(args.job, args.retries)
                    time.sleep(args.every)
                else:
                    now = datetime.datetime.now()
                    minute_key = (now.year, now.month, now.day, now.hour, now.minute)
                    if cron_matches(args.cron, now) and minute_key != last_minute:
                        last_minute = minute_key
                        run_once(args.job, args.retries)
                    time.sleep(20)  # wake twice per minute for cron precision
            except KeyboardInterrupt:
                print("\nstopped.")
                return
    finally:
        LOCK_FILE.unlink(missing_ok=True)


def cmd_log(args):
    if not LOG_FILE.exists():
        sys.exit(f"no log yet ({LOG_FILE})")
    entries = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if args.failures:
        entries = [e for e in entries if e["exit"] != 0]
    entries = entries[-args.tail:]
    for e in entries:
        status = "OK  " if e["exit"] == 0 else f"FAIL({e['exit']})"
        print(f"{e['ts']} {status:10s} {e['duration_s']:>7.2f}s r{e['retry']}  {e['job']}")
        if args.verbose and e.get("output_tail"):
            for line in e["output_tail"][-5:]:
                print(f"    | {line}")


def cmd_startup(args):
    """Print OS-native autostart config for the given command."""
    command = args.command
    cwd = Path.cwd()
    if sys.platform == "win32":
        xml = f"""<!-- Windows Task Scheduler — save as taskloop.xml, then run:
     schtasks /create /tn "TaskLoop" /xml taskloop.xml /f -->
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled></LogonTrigger>
  </Triggers>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>pythonw</Command>
      <Arguments>{command}</Arguments>
      <WorkingDirectory>{cwd}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""
        print(xml)
    elif sys.platform == "darwin":
        print(f"""<!-- macOS launchd — save as ~/Library/LaunchAgents/com.taskloop.job.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
  <key>Label</key><string>com.taskloop.job</string>
  <key>ProgramArguments</key><array>
    <string>python3</string>
{''.join(f'    <string>{p}</string>' for p in command.split())}
  </array>
  <key>WorkingDirectory</key><string>{cwd}</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>""")
    else:
        print(f"# Linux — add to crontab (crontab -e):")
        print(f"@reboot cd {cwd} && {command}")
    print(f"\n(printed only — nothing was installed. Run the shown steps as the user.)",
          file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(prog="taskloop",
                                     description="Scheduled job runner with logs and retries.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="run a job on a schedule")
    p.add_argument("job", help="command to run (shell string)")
    p.add_argument("--every", type=int, help="seconds between runs")
    p.add_argument("--cron", help="cron pattern 'M H dom mon dow' (local time)")
    p.add_argument("--retries", type=int, default=2, help="retries on failure (default 2)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("log", help="inspect run history")
    p.add_argument("--tail", type=int, default=20)
    p.add_argument("--failures", action="store_true")
    p.add_argument("--verbose", action="store_true", help="show output tail")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("startup", help="print OS-native autostart config")
    p.add_argument("command", help="full taskloop command to autostart")
    p.set_defaults(func=cmd_startup)

    args = parser.parse_args()
    if args.command == "run" and not args.every and not args.cron:
        sys.exit("error: --every SECONDS or --cron 'M H dom mon dow' required")
    args.func(args)


if __name__ == "__main__":
    main()
