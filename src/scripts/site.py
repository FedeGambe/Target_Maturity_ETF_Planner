"""Rigenera docs/dati.json (letto da index.html) a partire da data/yield_etf.csv."""
import csv
import json
from datetime import datetime

from scripts.support import ALIQUOTA_CORP, ALIQUOTA_GOVT, BASE

OUT = BASE.parent / "docs" / "dati.json"
f = lambda s: float(s.replace(",", ".")) if s else None
d = lambda s: datetime.strptime(s, "%d/%m/%Y")


def build():
    rows = list(csv.reader(open(BASE / "yield_etf.csv", encoding="utf-8-sig"), delimiter=";"))[1:]
    days = sorted({r[0] for r in rows}, key=d)
    aliq = {"Corp": ALIQUOTA_CORP, "Govt": ALIQUOTA_GOVT}
    etfs = {}
    for r in sorted(rows, key=lambda r: d(r[0])):  # l'ultima riga di un ISIN fissa i metadati
        t = "Corp" if r[4] == "Corporate" else r[4]
        e = etfs.setdefault(r[3], {"isin": r[3], "y": {}})
        e.update(n=r[2], em="iShares" if r[1].startswith("iShares") else r[1], t=t, p=r[5], a=d(r[6]).year,
                 sc=d(r[6]).strftime("%m/%Y"), ter=f(r[7]))
        e["y"][r[0]] = f(r[8])
    out = []
    for e in etfs.values():
        ys = [e["y"].get(x) for x in days]
        e["ny"] = [None if y is None else round((y - e["ter"]) * (1 - aliq[e["t"]]), 3) for y in ys]
        e["y"] = ys
        out.append(e)
    out.sort(key=lambda e: -(e["y"][-1] or 0))
    return {"base": d(days[-1]).year, "iso": [d(x).strftime("%Y-%m-%d") for x in days],
            "dates": [d(x).strftime("%d/%m") for x in days], "etfs": out, "aliq": aliq}, days[-1]


def update():
    data = build()[0]
    j = lambda x: json.dumps(x, ensure_ascii=False, separators=(", ", ": "))
    etfs = ",\n".join("    " + j(e) for e in data.pop("etfs"))  # un ETF per riga: leggibile e diff piccoli
    body = ",\n".join(f"  {j(k)}: {j(v)}" for k, v in data.items())
    OUT.write_text("{\n" + body + ",\n  " + '"etfs": [\n' + etfs + "\n  ]\n}\n", encoding="utf-8")


if __name__ == "__main__":
    update()
