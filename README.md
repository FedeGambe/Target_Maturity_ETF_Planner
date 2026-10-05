# Bond ETF target maturity analysis

Analisi dei **bond ETF a scadenza fissa (target maturity)**: scraper dei rendimenti e simulazione di un piano di accumulo per comprare un'auto.
Il versamento mensile è diviso tra conto deposito e una scala di ETF con scadenze diverse; i rendimenti vengono scaricati dai siti degli emittenti.

## Cosa fa

1. **Scraper** (`src/main.py`): legge i siti degli emittenti (Amundi, DWS Xtrackers, iShares iBonds, Invesco BulletShares, BNP Paribas Easy), estrae rendimento a scadenza (YTM), TER, cedola e scadenza, e li aggiunge allo storico `data/yield_etf.xlsx`.
2. **Foglio riepilogo**: da quello storico costruisce `data/rendimenti_etf.xlsx` con l'ultimo dato di ogni ETF, lordo e netto di TER e tasse (12,5% titoli di Stato, 26% corporate).
3. **Notebook** (`notebooks/`): legge il foglio e confronta piani diversi.

## Il notebook

Piano di esempio: €210/mese per 14 mensilità, diviso in conto deposito + 3 ETF con scadenze diverse (2029, 2031, 2033).

- alla prima scadenza il capitale viene reinvestito in un altro ETF; alle altre va sul conto deposito;
- **panorami**: le scadenze si spostano di ±1 anno e il tasso del conto deposito varia tra 1% e 2%;
- risultato: valore finale, XIRR, perdita stimata se i tassi salgono dell'1%, distanza dall'obiettivo.

Parametri all'inizio del notebook, tra cui `PROVENTI`: `("Acc",)`, `("Dist",)` o entrambi.

**Limiti**: il rendimento usato è lo YTM del giorno di estrazione, non una promessa. Gli ETF a distribuzione sono modellati come se la cedola fosse reinvestita allo stesso rendimento. Il rischio tassi è approssimato con la durata pari agli anni residui.

## Struttura

```
src/
  main.py            punto di ingresso dello scraper
  scripts/           scraper, esportazione xlsx, costanti e config.toml (URL, aliquote)
notebooks/           analisi e simulazione
data/                xlsx e log generati (non versionati)
```

## Uso

```
pip install -r requirements.txt
playwright install chromium

python src/main.py            # scarica, aggiorna lo storico e il foglio
python src/main.py --foglio   # ricostruisce solo il foglio dallo storico
```

Poi apri il notebook in `notebooks/`. Gli URL e le aliquote si cambiano in `src/scripts/config.toml`.

Eseguito con `pythonw` (ad esempio da Utilità di pianificazione di Windows) il log va in `data/logs/yield_scraper.log`.

## Avvertenza

Strumento personale a scopo di studio: non è consulenza finanziaria. I dati vengono da siti pubblici e il formato delle pagine può cambiare, rompendo lo scraper.
