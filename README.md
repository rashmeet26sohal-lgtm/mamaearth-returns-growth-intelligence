# Mamaearth Returns & Growth Intelligence Pipeline

A reproducible, three-layer capstone pipeline for order storage, pandas cleaning/EDA, and a Situation–Complication–Resolution (SCR) business narrative. All source CSVs are preserved as provided; cleaning happens in Python.

## Repository structure

```text
.
├── README.md
├── requirements.txt
├── sql/
│   ├── schema.sql
│   ├── seed_data.sql
│   └── reports.sql
├── data/
│   ├── customers.csv
│   ├── products.csv
│   └── orders.csv
├── analysis/
│   ├── clean_and_eda.py
│   └── visualize.py
├── visualizations/
│   ├── return_rate_by_payment.png
│   └── monthly_revenue_trend.png
└── narrator/
    ├── findings.json
    ├── generate_narrative.py
    └── sample_output.txt
```

## 1. SQL relational layer and reports

Use Python's built-in SQLite support or the SQLite CLI. From the repository root, the CLI sequence is:

```bash
sqlite3 mamaearth.db < sql/schema.sql
sqlite3 mamaearth.db < sql/seed_data.sql
sqlite3 mamaearth.db < sql/reports.sql
```

`schema.sql` creates the three related tables. `seed_data.sql` contains inserts generated from the supplied CSVs; blank `discount_pct` and `rating` fields are SQL `NULL`. The seed transaction clears and reloads the tables, so rerunning it restores the raw source state. Expected row counts after seeding: customers **45**, products **16**, orders **180**.

`reports.sql` contains the nine report exercises and expected outputs in comments. The final ALTER TABLE task adds `loyalty_tier`; run that report section once per freshly seeded database (or recreate the database before repeating the full reports script).

The SQL layer intentionally reports the raw, uncleaned order data. Report (a) yields raw revenue **₹99,860.20** and average order value **₹554.78**.

## 2. Python cleaning, EDA, and visualizations

Install the dependencies and run the analysis in this order:

```bash
python -m pip install -r requirements.txt
python analysis/clean_and_eda.py
python analysis/visualize.py
```

`clean_and_eda.py` reads the three raw CSVs independently of SQLite. It prints input shapes, payment-method normalization, duplicate IDs, imputation counts, the independently calculated duplicate revenue delta, IQR outliers, return-rate hypothesis test, payment-by-city-tier segments, all correlation pairs and the two monthly revenue series.

At the end of Task 5/Part 2, the analysis script computes and writes **`narrator/findings.json`** from its measured results. This is the handoff from the analysis layer to the narrator; the JSON is not manually maintained. The visualizer reuses the same cleaning logic and regenerates the two PNGs under `visualizations/`.

Key expected results include cleaned revenue **₹97,358.30**, duplicate reconciliation delta **₹2,501.90**, COD return rate **44.4%**, and highest-risk COD/Tier-2 segment **54.5%**. The outlier-corrected peak is **March 2026 at ₹20,318.90**; January's apparent **₹29,582.10** is inflated by two bulk-quantity rows and falls to **₹11,637.10** after excluding those flagged rows from the monthly comparison. Outliers are flagged, not deleted from the cleaned dataset.

## 3. SCR narrator: Gemini API or offline fallback

Run:

```bash
python narrator/generate_narrative.py
```

The script reads `narrator/findings.json`, builds a Situation / Complication / Resolution narrative, checks required numeric facts, and saves the output to `narrator/sample_output.txt`.

**Free Gemini path:** Google AI Studio offers a Gemini API key with a free usage tier, subject to current quotas and availability. Set the key as an environment variable; do not put secrets in source control.

macOS/Linux:
```bash
export GEMINI_API_KEY="your-google-ai-studio-key"
python narrator/generate_narrative.py
```

Windows PowerShell:
```powershell
$env:GEMINI_API_KEY="your-google-ai-studio-key"
python narrator/generate_narrative.py
```

The code also accepts `GOOGLE_API_KEY`. `GEMINI_MODEL` optionally selects a model; default is `gemini-2.5-flash`. If no key is configured, the script runs `generate_scr_narrative_offline(findings)` automatically. If a configured Gemini request fails, it reports the error and falls back to the same deterministic offline template. The offline route needs no key, network access, or API spend, so the pipeline remains runnable in a fully keyless environment. The checked-in `sample_output.txt` is the generated offline sample; if you run the online route successfully, the script replaces it with that actual response and runs the same numeric checklist.

## Pipeline data flow

1. Raw CSVs → SQLite schema/seed → raw SQL reports.
2. The same untouched CSVs → pandas cleaning and EDA → `narrator/findings.json` plus charts.
3. `findings.json` → Gemini SCR narrative when configured, otherwise deterministic offline SCR narrative → numeric accuracy checker and `sample_output.txt`.

## Expected quality checks

- Raw source row counts: 45 customers, 16 products, 180 orders.
- Standardized payment counts before deduplication: CARD 70, UPI 55, COD 55.
- Five duplicate rows removed by natural key: O0176–O0180.
- Missing values imputed after deduplication: 12 discount values and 15 ratings; median rating 3.0.
- IQR quantity outliers flagged: O0011 (25) and O0098 (30).
- Return rates: CARD 14.7%, COD 44.4%, UPI 18.9%.
- Highest-risk segment: COD / Tier-2, 54.5%.
- Corrected monthly revenue peak: 2026-03, ₹20,318.90.
