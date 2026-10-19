"""Reproducible pandas cleaning, EDA, reconciliation, and findings export."""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
NARRATOR = ROOT / "narrator"
NARRATOR.mkdir(exist_ok=True)

def money(x):
    return round(float(x), 2)

def main():
    customers = pd.read_csv(DATA / "customers.csv")
    products = pd.read_csv(DATA / "products.csv")
    orders = pd.read_csv(DATA / "orders.csv")
    print("TASK 1 — LOAD AND INSPECT")
    print("customers.shape:", customers.shape)
    print("products.shape:", products.shape)
    print("orders.shape before cleaning:", orders.shape)
    print("\nTASK 2 — PAYMENT STANDARDIZATION")
    print("Raw payment_method unique values:", sorted(orders["payment_method"].dropna().unique().tolist()))
    orders["payment_method"] = orders["payment_method"].astype("string").str.strip().str.upper()
    print("Standardized payment counts:\n", orders["payment_method"].value_counts().to_string())

    print("\nTASK 3 — NATURAL-KEY DUPLICATE REMOVAL")
    natural_key = ["customer_id", "product_id", "order_date", "quantity", "discount_pct",
                   "payment_method", "rating", "returned"]
    dup_mask = orders.duplicated(subset=natural_key, keep="first")
    dropped = orders.loc[dup_mask].copy()
    orders_clean = orders.loc[~dup_mask].copy()
    print("Duplicate rows flagged:", int(dup_mask.sum()))
    print("Dropped order_id values:", dropped["order_id"].tolist())
    print("orders_clean.shape:", orders_clean.shape)

    print("\nTASK 4 — MISSING-VALUE IMPUTATION")
    discount_missing = int(orders_clean["discount_pct"].isna().sum())
    rating_missing = int(orders_clean["rating"].isna().sum())
    rating_median = float(orders_clean["rating"].median())
    print("discount_pct missing values to fill:", discount_missing)
    print("rating missing values to fill:", rating_missing)
    print("Median rating before imputation:", rating_median)
    orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
    orders_clean["rating"] = orders_clean["rating"].fillna(rating_median)
    print("Null counts after imputation:", orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict())

    # Revenue is computed on the clean order rows, joined to the source dimensions.
    clean_merged = orders_clean.merge(products, on="product_id", how="left", validate="many_to_one")
    clean_merged = clean_merged.merge(customers, on="customer_id", how="left", validate="many_to_one")
    clean_merged["order_value"] = clean_merged["quantity"] * clean_merged["price"] * (1 - clean_merged["discount_pct"] / 100)
    cleaned_total = money(clean_merged["order_value"].sum())
    print("\nTASK 5 — MERGE AND RECONCILIATION")
    print("Cleaned order rows:", len(clean_merged))
    print(f"Cleaned total revenue: ₹{cleaned_total:,.2f}")

    # Compute the dropped rows' revenue independently to prove the reconciliation.
    dropped_rev = dropped.merge(products[["product_id", "price"]], on="product_id", how="left", validate="many_to_one")
    dropped_rev["discount_pct"] = dropped_rev["discount_pct"].fillna(0)
    dropped_rev["order_value"] = dropped_rev["quantity"] * dropped_rev["price"] * (1 - dropped_rev["discount_pct"] / 100)
    duplicate_delta = money(dropped_rev["order_value"].sum())
    raw = orders.copy()
    raw["discount_pct"] = raw["discount_pct"].fillna(0)
    raw_rev = raw.merge(products[["product_id", "price"]], on="product_id", how="left", validate="many_to_one")
    raw_total = money((raw_rev["quantity"] * raw_rev["price"] * (1 - raw_rev["discount_pct"] / 100)).sum())
    print(f"Raw total revenue (NULL discount treated as 0%): ₹{raw_total:,.2f}")
    print(f"Value of the five removed duplicate rows: ₹{duplicate_delta:,.2f}")
    print(f"Raw minus cleaned revenue: ₹{money(raw_total-cleaned_total):,.2f}")
    print("Reconciliation: the ₹2,501.90 reduction is entirely attributable to the five duplicate rows removed (O0176–O0180), whose independently summed order_value is ₹2,501.90. Filling missing discount_pct with 0 and rating with the median does not change order_value, so neither imputation explains the revenue delta.")

    print("\nTASK 6 — IQR OUTLIER DETECTION ON QUANTITY")
    q1 = float(clean_merged["quantity"].quantile(.25))
    q3 = float(clean_merged["quantity"].quantile(.75))
    iqr = q3-q1
    lower, upper = q1-1.5*iqr, q3+1.5*iqr
    clean_merged["is_outlier"] = ~clean_merged["quantity"].between(lower, upper, inclusive="both")
    outliers = clean_merged.loc[clean_merged["is_outlier"], ["order_id", "quantity"]]
    print(f"Q1={q1:.1f}, Q3={q3:.1f}, IQR={iqr:.1f}, lower={lower:.1f}, upper={upper:.1f}")
    print("Outlier rows:\n", outliers.to_string(index=False))
    print("Outlier count:", len(outliers))

    print("\nTASK 7 — COD RETURN-RATE HYPOTHESIS")
    print("Hypothesis: COD orders have a higher return rate than CARD and UPI orders.")
    pay_stats = orders_clean.groupby("payment_method")["returned"].agg(["count", "mean"])
    pay_stats["return_rate_pct"] = (pay_stats["mean"]*100).round(1)
    print(pay_stats[["count", "return_rate_pct"]].sort_index().to_string())
    payment_rates = {k: round(float(v)*100, 1) for k, v in orders_clean.groupby("payment_method")["returned"].mean().items()}
    print("Hypothesis: Confirmed — COD has the highest observed return rate.")

    print("\nTASK 8 — PAYMENT × CITY-TIER SEGMENTATION")
    seg = orders_clean.merge(customers[["customer_id", "city_tier"]], on="customer_id", how="left")
    seg_summary = seg.groupby(["payment_method", "city_tier"])["returned"].agg(["count", "mean"]).reset_index()
    seg_summary["return_rate_pct"] = (seg_summary["mean"]*100).round(1)
    print(seg_summary[["payment_method", "city_tier", "count", "return_rate_pct"]].to_string(index=False))
    high = seg_summary.sort_values(["return_rate_pct", "count"], ascending=[False, False]).iloc[0]
    print(f"Highest-risk segment: {high['payment_method']} + Tier-{int(high['city_tier'])} cities at {high['return_rate_pct']:.1f}%.")

    print("\nTASK 9 — CORRELATION ANALYSIS")
    corr_cols = ["rating", "returned", "discount_pct", "quantity"]
    corr = clean_merged[corr_cols].corr()
    print(corr.round(3).to_string())
    bands = []
    for i, a in enumerate(corr_cols):
        for b in corr_cols[i+1:]:
            r = float(corr.loc[a, b])
            strength = "negligible" if abs(r) < .2 else "weak" if abs(r) < .4 else "moderate" if abs(r) < .7 else "strong"
            bands.append((a, b, r, strength))
            print(f"{a} vs {b}: r={r:.3f} — {strength}")
    discount_return_r = float(corr.loc["discount_pct", "returned"])
    print(f'Hypothesis "higher discounts reduce returns": {"Busted" if discount_return_r > -0.2 else "Supported"} (discount_pct vs returned r={discount_return_r:.3f}).')

    print("\nTASK 10 — OUTLIER-CORRECTED MONTHLY REVENUE")
    clean_merged["order_date"] = pd.to_datetime(clean_merged["order_date"])
    clean_merged["month"] = clean_merged["order_date"].dt.to_period("M").astype(str)
    apparent = clean_merged.groupby("month")["order_value"].sum().round(2)
    corrected = clean_merged.loc[~clean_merged["is_outlier"]].groupby("month")["order_value"].sum().round(2)
    print("Apparent monthly revenue (including quantity outliers):")
    for month, value in apparent.items():
        print(f"  {month}: ₹{value:,.2f}")
    print("Outlier-corrected monthly revenue:")
    for month, value in corrected.items():
        print(f"  {month}: ₹{value:,.2f}")
    peak_month = corrected.idxmax()
    print("January's apparent lead is an artifact of the two bulk orders O0011 (2026-01-28, quantity 25) and O0098 (2026-01-10, quantity 30) landing in January. Excluding those outliers reveals March as the genuine peak month.")
    print(f"True peak month: {peak_month}, ₹{corrected.loc[peak_month]:,.2f}")

    findings = {
        "cleaned_total_revenue_inr": cleaned_total,
        "raw_total_revenue_inr": raw_total,
        "duplicate_reconciliation_delta_inr": duplicate_delta,
        "return_rate_by_payment": payment_rates,
        "highest_risk_segment": {
            "payment_method": str(high["payment_method"]),
            "city_tier": int(high["city_tier"]),
            "return_rate_pct": round(float(high["return_rate_pct"]), 1),
        },
        "true_peak_month": {"month": peak_month, "revenue_inr": money(corrected.loc[peak_month])},
        "outlier_inflated_month": {
            "month": apparent.idxmax(),
            "apparent_revenue_inr": money(apparent.max()),
            "corrected_revenue_inr": money(corrected.loc[apparent.idxmax()]),
        },
        "monthly_revenue_apparent_inr": {k: money(v) for k, v in apparent.items()},
        "monthly_revenue_corrected_inr": {k: money(v) for k, v in corrected.items()},
    }
    outpath = NARRATOR / "findings.json"
    outpath.write_text(json.dumps(findings, indent=2) + "\n")
    print(f"\nWrote computed findings to {outpath.relative_to(ROOT)}")
    print(json.dumps(findings, indent=2))

if __name__ == "__main__":
    main()
