"""Estrazione del rendimento a scadenza dai siti degli emittenti.
Ogni funzione ritorna tuple (emittente, nome, isin, proventi, ter, ytm, data_dato, cedola, nav, data_nav)."""
import re
from datetime import date, datetime, timezone

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from scripts.support import AMUNDI_URL, DWS_URL, INVESCO_URL, ISHARES_TABS, ISHARES_URL, UA, pct


def amundi(page):
    # "Rendimento**" in scheda prodotto = BENCHMARK_LAST_INDEX_PRICE.nominalYield dell'API che la pagina lista chiama da sola
    with page.expect_response(lambda r: "ProductAPI/getProductsData" in r.url, timeout=90000) as resp:
        page.goto(AMUNDI_URL, wait_until="domcontentloaded")
    isins = [p["productId"] for p in resp.value.json()["products"]]
    # stessa API, chiesta di nuovo con i campi che servono (la pagina lista non chiede DISTRIBUTION_POLICY)
    data = requests.post("https://www.amundietf.it/mapi/ProductAPI/getProductsData", headers=UA, json={
        "context": {"countryCode": "ITA", "userProfileName": "INSTIT"}, "productIds": isins, "metrics": [],
        "characteristics": ["SHARE_MARKETING_NAME", "ISIN", "DISTRIBUTION_POLICY", "TER", "BENCHMARK_LAST_INDEX_PRICE", "NAV", "NAV_DATE_DISPLAYED"]}).json()
    rows = []
    for p in data["products"]:
        c = p["characteristics"]
        b = c["BENCHMARK_LAST_INDEX_PRICE"]
        rows.append(("Amundi", c["SHARE_MARKETING_NAME"], c["ISIN"], c.get("DISTRIBUTION_POLICY", ""), c.get("TER"),
                     round(b["nominalYield"] * 100, 2), f"{date.fromisoformat(b['indexPriceDate']):%d/%m/%Y}",
                     round(b["weightedAverageCoupon"], 2) if b.get("weightedAverageCoupon") is not None else None,
                     c.get("NAV"), f"{datetime.fromtimestamp(c['NAV_DATE_DISPLAYED'] / 1000, timezone.utc):%d/%m/%Y}"
                     if c.get("NAV_DATE_DISPLAYED") else ""))  # "Ultima NAV" della scheda prodotto; data in ms epoch
    return rows


def dws(page):
    # ponytail: entry gate DWS accettato una volta (Italia / retail, cookie non essenziali rifiutati), il contesto lo ricorda
    with page.expect_response(lambda r: "fundfinder/it-it/datatable" in r.url and '"filters":[{' in (r.request.post_data or ""), timeout=90000) as resp:
        page.goto(DWS_URL, wait_until="domcontentloaded")
        page.get_by_role("button", name="Non accetto").click()
        page.get_by_role("button", name="Accetta & continua").click()
    rows = []
    for v in resp.value.json()["values"]:
        link = v["ProductNameIsin"]["ProductNameIsin_0"]["value"]
        page.goto("https://etf.dws.com" + link["url"], wait_until="networkidle")
        text = page.inner_text("body")
        m = re.search(r"Rendimento a scadenza\s+(?:Rendimento a scadenza\s+)?(-?[\d.,]+\s*%)", text)
        d = re.search(r"Rendimento a scadenza.*?Al (\d{2}/\d{2}/\d{4})", text, re.S)
        c = re.search(r"Cedola\s+(?:Cedola\s+)?(-?[\d.,]+\s*%)", text)
        n = re.search(r"NAV\s+Al (\d{2}/\d{2}/\d{4})\s+(-?[\d.,]+)\s*EUR", text)
        rows.append(("DWS", link["text"], v["ID"]["value"], v["UseOfProfit"]["value"], v["TotalExpenseRatio"]["sortValue"],
                     pct(m.group(1)) if m else None, d.group(1) if d else "", pct(c.group(1)) if c else None,
                     pct(n.group(2)) if n else None, n.group(1) if n else ""))
    return rows


def invesco(page):
    # API Invesco protetta da anti-bot (406 fuori dal browser): lista presa dalle risposte della pagina,
    # "Stima YTM" chiesta con fetch dall'interno della pagina. Solo classi in EUR, come per iShares.
    is_search = lambda r: "dng-api.invesco.com/product/search" in r.url and "BulletShares" in r.url
    is_listing = lambda r: "shareclasses?" in r.url and r.request.method == "POST"
    with page.expect_response(is_listing, timeout=90000) as listing, page.expect_response(is_search, timeout=90000) as search:
        page.goto(INVESCO_URL, wait_until="domcontentloaded")
    ter = {x["isin"]: x.get("terocf") for x in listing.value.json()}
    rows = []
    for doc in search.value.json()["response"]["docs"]:
        name, isin = doc["title"], doc["isin"]
        if " EUR " not in name:
            continue
        stats = page.evaluate("async u => (await fetch(u)).json()",
                              f"https://dng-api.invesco.com/cache/v1/accounts/it_IT/shareclasses/{isin}/keyStats?idType=isin&productCode=ETF&bondType=NotCallable")
        ytm = next((s for s in stats["keyStats"] if s["name"] == "yieldToMaturity"), None)
        nav = next((s for s in stats["keyStats"] if s["name"] == "nav"), None)
        info = page.evaluate("async u => (await fetch(u)).json()",
                             f"https://dng-api.invesco.com/cache/v1/accounts/it_IT/shareclasses/{isin}/characteristics?idType=isin&audienceType=Financial%20Professional&variationType=portfolioInformation")
        rows.append(("Invesco", name, isin, name.split()[-1], ter.get(isin),
                     round(ytm["value"], 2) if ytm else None,
                     f"{date.fromisoformat(ytm['asOfDate']):%d/%m/%Y}" if ytm else "",
                     round(info["averageWeightedCoupon"], 2) if info.get("averageWeightedCoupon") is not None else None,
                     round(nav["value"], 4) if nav else None,
                     f"{date.fromisoformat(nav['asOfDate']):%d/%m/%Y}" if nav else ""))
    return rows


def bnp():
    # API pubbliche BNP (quelle che usano lista e scheda): nessun popup da passare. ETF obbligazionari con l'anno nel nome.
    base = "https://api.bnpparibas-am.com/push"
    shares = requests.get(f"{base}/sharesearchv2/PV_IT-FSE/ITA", headers=UA).json()["shares"]
    rows = []
    for s in shares:
        name = s["legal_name"] or ""
        if s.get("prod_channel1") != "ETF/Index" or s.get("asset_class") != "Reddito fisso" \
                or "UCITS ETF" not in name or not re.search(r"\b20\d\d\b", name):
            continue
        fs = requests.get(f"{base}/fundsheet/PV_IT-FSE/ITA/ITA/{s['isin_code'].lower()}", headers=UA).json()
        ter = fs.get("fees", {}).get("fees_timed", {}).get("real_ongoing_charges", {}).get("value")
        nav = fs["nav"]["two_latest_nav"]["EUR"][0]
        # "YtM" del Simulatore del Rendimento a scadenza (tab Performance), calcolato sull'ultimo NAV:
        # lordo, come per gli altri emittenti (TER e tasse li toglie il foglio)
        sim = requests.get("https://api.bnpparibas-am.com/backtest/ytm-simulator", headers=UA, params={
            "fund_isin_code": s["isin_code"], "ocr": ter or 0, "nominal": 10000,
            "projected_nav": round(nav["nav"], 2), "latest_nav": nav["nav"]}).json()
        holdings = requests.get(f"{base}/holdings/ITA/{s['share_id']}", headers=UA).json()
        coupon = holdings.get("average_coupon_rate", {}).get("ptf_value")  # cedola media del portafoglio (dato di fine mese)
        rows.append(("BNP Paribas", name, s["isin_code"], s["dividend_policy"], float(ter) if ter else None,
                     float(sim["ytm"].rstrip("%")) if sim.get("ytm") else None,  # formato inglese "3.93%"
                     f"{date.fromisoformat(nav['date']):%d/%m/%Y}", round(coupon, 2) if coupon is not None else None,
                     nav["nav"], f"{date.fromisoformat(nav['date']):%d/%m/%Y}"))
    return rows


def ishares():
    s = requests.Session()
    s.headers.update(UA)
    soup = BeautifulSoup(s.get(ISHARES_URL).text, "html.parser")
    labels = [t["label"] for t in soup.find_all("ds-tab", attrs={"legend": True})]
    panels = [t for t in soup.find_all("ds-tab") if not t.has_attr("legend") and t.find("ds-fund-card-api")]
    rows = []
    for label, panel in zip(labels[-len(panels):], panels):
        if label not in ISHARES_TABS:
            continue
        for card in panel.find_all("ds-fund-card-api"):
            r = s.get(card["fund-url"] + "?switchLocale=y&siteEntryPassthrough=true")
            r.encoding = "utf-8"
            ps = BeautifulSoup(r.text, "html.parser")
            name = ps.title.text.split("|")[0].strip()
            if label == "Government Bonds" and "€" not in name:
                continue
            li = ps.select_one("li.yieldToWorst")
            as_of = re.search(r"\d{2}/\d{2}/\d{4}", li.select_one(".header-nav-label").text) if li else None
            use = ps.select_one(".col-useOfProfitsCode .data")
            ter = ps.select_one(".col-emeaMgt .data")
            coupon = ps.select_one(".col-weightedAvgCoupon .data")
            nav = re.search(r"NAV al (\d{2}/\d{2}/\d{4})\s+\w+\s+(-?[\d.,]+)", ps.select_one("li.navAmount").text) if ps.select_one("li.navAmount") else None
            rows.append(("iShares", name, re.search(r'var isin = "(\w+)"', r.text).group(1),
                         use.text.strip() if use else "", pct(ter.text) if ter else None,
                         pct(li.select_one(".header-nav-data").text) if li else None, as_of.group(0) if as_of else "",
                         pct(coupon.text) if coupon and "%" in coupon.text else None,
                         pct(nav.group(2)) if nav else None, nav.group(1) if nav else ""))
    return rows


def _try(fn, *args, retries=2):
    """Esegue lo scraper di un emittente; ritenta, poi ritorna [] e segnala l'errore senza fermare gli altri."""
    for n in range(1, retries + 1):
        try:
            return fn(*args)
        except Exception as e:
            print(f"ATTENZIONE {fn.__name__} fallito (tentativo {n}/{retries}): {type(e).__name__}: {str(e).splitlines()[0]}")
    return []


def scrape_all():
    rows = _try(ishares) + _try(bnp)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_context(locale="it-IT", user_agent=UA["User-Agent"]).new_page()
            page.set_default_navigation_timeout(90000)
            for fn in (amundi, dws, invesco):
                rows += _try(fn, page)
        finally:
            browser.close()
    return rows
