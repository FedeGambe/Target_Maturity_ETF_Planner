"""Costanti, configurazione e funzioni di utilità condivise."""
import calendar
import re
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BASE = ROOT / "data"  # output in data/, anche se lanciato dall'Utilità di pianificazione
CONFIG = tomllib.loads((Path(__file__).resolve().parent / "config.toml").read_text(encoding="utf-8"))
ALIQUOTA_GOVT = CONFIG["aliquote"]["govt"]
ALIQUOTA_CORP = CONFIG["aliquote"]["corp"]

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}

AMUNDI_URL, DWS_URL, ISHARES_URL, INVESCO_URL = (CONFIG["url"][k] for k in ("amundi", "dws", "ishares", "invesco"))
ISHARES_TABS = set(CONFIG["ishares"]["tabs"])

PROVENTI = {"distribution": "Dist", "distribuzione": "Dist", "dist": "Dist", "d": "Dist",
            "accumulation": "Acc", "accumulazione": "Acc", "ad accumulazione": "Acc",
            "capitalisation": "Acc", "capitalizzazione": "Acc", "acc": "Acc", "c": "Acc"}
MESI = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}

num = lambda x: "" if x is None else str(x).replace(".", ",")


def pct(text):
    """'2,75%' -> 2.75"""
    return float(text.replace("%", "").replace(".", "").replace(",", ".").strip())


def tipo(name):
    return "Govt" if re.search(r"Gov|Treasury|BTP|Bund", name) else "Corp"


def pulisci(name):
    """Nome senza punteggiatura: 'EASY ... 2029 [UCITS ETF, D]' -> 'EASY ... 2029 UCITS ETF D'."""
    return " ".join(re.sub(r"[()\[\],.:;]", " ", name).split())


def scadenza(name):
    """Nessun sito espone la data di scadenza del fondo: la ricavo dal nome, all'ultimo giorno del mese.
    'Sept 2029' -> '30/09/2029'; solo anno -> dicembre: '2027' -> '31/12/2027'."""
    m = re.search(r"\b(?:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\w*\s+)?(20\d\d)\b", name)
    if not m:
        return ""
    year, month = int(m.group(2)), MESI[m.group(1)[:3].lower()] if m.group(1) else 12
    return f"{calendar.monthrange(year, month)[1]:02d}/{month:02d}/{year}"


def months_back(d, n):
    """Stessa data n mesi prima, col giorno limitato alla fine del mese (31/05 - 3 mesi -> 28/02)."""
    y, m = divmod(d.year * 12 + d.month - 1 - n, 12)
    return d.replace(year=y, month=m + 1, day=min(d.day, calendar.monthrange(y, m + 1)[1]))


def selfcheck():
    assert pct("2,75%") == 2.75 and pct("-0,5 %") == -0.5 and pct("1.234,5%") == 1234.5
    assert scadenza("iShares iBonds Dec 2027 Term € Corp") == "31/12/2027"
    assert scadenza("Xtrackers II Target Maturity Sept 2029 EUR Corporate Bond") == "30/09/2029"
    assert scadenza("Amundi Fixed Maturity 2028 Euro Government Bond") == "31/12/2028"
    assert tipo("iShares iBonds Dec 2028 Term € Italy Govt Bond") == "Govt"
    assert tipo("iShares iBonds Dec 2029 Term € Corp Crossover") == "Corp"
    assert pulisci("BNP PARIBAS EASY CORP BOND DECEMBER 2029 [UCITS ETF, D]") == "BNP PARIBAS EASY CORP BOND DECEMBER 2029 UCITS ETF D"
    assert months_back(date(2026, 5, 31), 3) == date(2026, 2, 28) and months_back(date(2026, 1, 15), 1) == date(2025, 12, 15)
