"""Scarica il rendimento a scadenza degli ETF a scadenza fissa (Amundi, DWS Xtrackers, iShares iBonds, Invesco BulletShares, BNP Paribas Easy).
Aggiunge ogni estrazione allo storico data/yield_etf.csv (con filtri) e ricostruisce da lì data/rendimenti_etf.xlsx con l'ultimo dato di ogni ETF, lordo e netto.

    python src/main.py             estrae, aggiorna lo storico e il foglio
    python src/main.py --foglio    solo ricostruisce il foglio dallo storico, senza estrarre"""
import csv
import sys
from datetime import date, datetime

from scripts.exporter import HISTORY, append_history, build_sheet
from scripts.scrapers import scrape_all
from scripts.support import BASE, PROVENTI, scadenza, selfcheck, tipo


def main():
    today = f"{date.today():%d/%m/%Y}"
    rows = [(today, issuer, name, isin, tipo(name), PROVENTI.get(use.lower(), use), scadenza(name), ter, ytm, as_of, coupon, nav, nav_date)
            for issuer, name, isin, use, ter, ytm, as_of, coupon, nav, nav_date in scrape_all()]
    if HISTORY.exists():  # estrazione incompleta (emittente caduto): non sporcare lo storico, il job ritenta
        with open(HISTORY, encoding="utf-8-sig") as f:
            dates = [r[0] for r in csv.reader(f, delimiter=";")][1:]
        prev = dates.count(dates[-1]) if dates else 0
        if len(rows) < prev - 2:  # tolleranza: un ETF scaduto sparisce dai siti
            sys.exit(f"ERRORE estrazione incompleta: {len(rows)} ETF contro {prev} dell'ultima volta, storico non aggiornato")
    for r in rows:
        print(f"{r[3]}  {r[4]:<5} {r[5]:<5} {r[6]} TER {r[7]!s:<5} YTM {r[8]!s:>5} cedola {r[10]!s:>5} NAV {r[11]!s:>8}  {r[2]}")
    append_history(rows)
    print(f"\n{datetime.now():%Y-%m-%d %H:%M} - {len(rows)} ETF aggiunti a {HISTORY.name}")


if __name__ == "__main__":
    if sys.stdout is None:  # lanciato con pythonw (schedulato, senza finestra): output ed errori nel log
        (BASE / "logs").mkdir(exist_ok=True)  # su un clone nuovo data/logs non esiste
        sys.stdout = sys.stderr = open(BASE / "logs" / "yield_scraper.log", "a", encoding="utf-8")
    selfcheck()
    if "--foglio" not in sys.argv:
        main()
    build_sheet()
