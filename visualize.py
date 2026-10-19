"""Create the two required charts from raw data using the same cleaning rules."""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "visualizations"
OUT.mkdir(exist_ok=True)

orders = pd.read_csv(DATA / "orders.csv")
products = pd.read_csv(DATA / "products.csv")
orders["payment_method"] = orders["payment_method"].astype("string").str.strip().str.upper()
key = ["customer_id", "product_id", "order_date", "quantity", "discount_pct", "payment_method", "rating", "returned"]
orders = orders.loc[~orders.duplicated(subset=key, keep="first")].copy()
orders["discount_pct"] = orders["discount_pct"].fillna(0)
orders["rating"] = orders["rating"].fillna(orders["rating"].median())
df = orders.merge(products, on="product_id", how="left")
df["order_value"] = df["quantity"] * df["price"] * (1-df["discount_pct"]/100)
pay = df.groupby("payment_method")["returned"].mean().mul(100).sort_values(ascending=False)
fig, ax = plt.subplots(figsize=(8, 5))
bars = ax.bar(pay.index, pay.values)
ax.bar_label(bars, labels=[f"{v:.1f}%" for v in pay.values], padding=3)
ax.set_ylabel("Return rate (%)")
ax.set_xlabel("Payment method")
ax.set_title(f"COD Returns at {pay.get('COD', 0):.1f}% — {pay.get('COD', 0)/pay.get('CARD', 1):.1f}x Card")
ax.set_ylim(0, max(pay.values)*1.18)
fig.tight_layout()
fig.savefig(OUT / "return_rate_by_payment.png", dpi=160)
plt.close(fig)

df["quantity_outlier"] = ~df["quantity"].between(df["quantity"].quantile(.25)-1.5*(df["quantity"].quantile(.75)-df["quantity"].quantile(.25)),
                                                  df["quantity"].quantile(.75)+1.5*(df["quantity"].quantile(.75)-df["quantity"].quantile(.25)), inclusive="both")
df["month"] = pd.to_datetime(df["order_date"]).dt.to_period("M").astype(str)
monthly = df.loc[~df["quantity_outlier"]].groupby("month")["order_value"].sum()
peak = monthly.idxmax()
fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(monthly.index, monthly.values, marker="o")
ax.set_ylabel("Revenue (INR)")
ax.set_xlabel("Month")
ax.set_title(f"Outlier-Corrected Monthly Revenue — Peak: {peak}")
ax.grid(True, alpha=.25)
fig.tight_layout()
fig.savefig(OUT / "monthly_revenue_trend.png", dpi=160)
plt.close(fig)
print("Saved visualizations/return_rate_by_payment.png")
print("Saved visualizations/monthly_revenue_trend.png")
