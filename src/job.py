"""Job schedulato: lancia main.py (max 3 tentativi), se riesce committa e pusha i dati su GitHub, altrimenti avvisa con una notifica.
    pythonw src/job.py"""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "logs" / "yield_scraper.log"
RETRIES, WAIT = 3, 600  # tentativi, secondi tra l'uno e l'altro
NOWIN = subprocess.CREATE_NO_WINDOW


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M} [job] {msg}\n")


def run(*cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NOWIN)


def notify(text):
    ps = ("Add-Type -AssemblyName System.Windows.Forms;$n=New-Object Windows.Forms.NotifyIcon;"
          "$n.Icon=[Drawing.SystemIcons]::Error;$n.Visible=$true;"
          f"$n.ShowBalloonTip(15000,'Target Maturity ETF','{text}','Error');Start-Sleep 16;$n.Dispose()")
    subprocess.Popen(["powershell", "-NoProfile", "-Command", ps], creationflags=NOWIN)


def main():
    for n in range(1, RETRIES + 1):
        r = run(sys.executable.replace("pythonw", "python"), "src/main.py")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(r.stdout + r.stderr)
        if r.returncode == 0 and "ETF aggiunti" in r.stdout:
            break
        log(f"tentativo {n}/{RETRIES} fallito (exit {r.returncode})")
        if n < RETRIES:
            time.sleep(WAIT)
    else:
        log("FALLITO: nessun dato aggiunto")
        return notify("Estrazione fallita dopo 3 tentativi: controlla data/logs/yield_scraper.log")
    run("git", "add", "data/yield_etf.csv", "data/rendimenti_etf.xlsx")
    c = run("git", "commit", "-m", f"Aggiorna yield_etf {datetime.now():%d/%m/%Y}")
    p = run("git", "push") if c.returncode == 0 else c
    log("OK, dati su GitHub" if p.returncode == 0 else f"dati estratti ma commit/push falliti: {(p.stderr or p.stdout).strip()[:200]}")
    if p.returncode != 0:
        notify("Dati estratti ma commit/push su GitHub falliti: vedi log")


if __name__ == "__main__":
    main()
