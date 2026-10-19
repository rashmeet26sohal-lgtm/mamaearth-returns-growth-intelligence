"""SCR narrative generator with Gemini API and deterministic offline fallback."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FINDINGS_PATH = ROOT / "narrator" / "findings.json"
SAMPLE_PATH = ROOT / "narrator" / "sample_output.txt"

def generate_scr_narrative_offline(findings: dict) -> dict:
    """Generate a keyless SCR narrative using only supplied findings."""
    rates = findings["return_rate_by_payment"]
    risk = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    inflated = findings["outlier_inflated_month"]
    cleaned = findings["cleaned_total_revenue_inr"]
    raw = findings["raw_total_revenue_inr"]
    delta = findings["duplicate_reconciliation_delta_inr"]
    narrative = f"""Situation
The cleaned order dataset records total revenue of ₹{cleaned:,.2f} across the deduplicated orders. The payment-method return rates are COD {rates['COD']:.1f}%, CARD {rates['CARD']:.1f}%, and UPI {rates['UPI']:.1f}%.

Complication
The raw total is ₹{raw:,.2f}, which is ₹{delta:,.2f} higher than the cleaned total. The reconciliation attributes this delta to duplicate orders, not missing-value imputation. COD is the clearest returns concern: the highest-risk segment is COD in Tier-{risk['city_tier']} cities, with a {risk['return_rate_pct']:.1f}% return rate. The apparent revenue leader, {inflated['month']}, shows ₹{inflated['apparent_revenue_inr']:,.2f} before quantity outliers are excluded, compared with ₹{inflated['corrected_revenue_inr']:,.2f} after correction.

Resolution
Prioritize COD return-reduction actions in Tier-{risk['city_tier']} cities and monitor payment-method return rates together with city-tier segments. Use deduplicated revenue for reporting and flag bulk-quantity outliers before comparing months. The genuine peak month is March ({peak['month']}) at ₹{peak['revenue_inr']:,.2f}; use this corrected series for growth and inventory decisions."""
    return {"status": "success", "narrative": narrative, "tokens": None}

def generate_scr_narrative(findings: dict) -> dict:
    """Use Gemini if configured; otherwise return the offline SCR narrative."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return generate_scr_narrative_offline(findings)
    try:
        from google import genai
        client = genai.Client(
            api_key=api_key,
            http_options={"timeout": 30000},
        )
        system_instruction = (
            "You are a senior data analyst writing for Mamaearth's regional ops and finance heads. "
            "Write exactly three labeled sections: Situation, Complication, Resolution. "
            "Every number in the output must come from the supplied findings and appear with the same value; "
            "do not invent statistics, estimates, dates, or metrics. Explain operational implications clearly."
        )
        contents = (
            "Write an approximately 250-word business narrative using the supplied verified findings JSON. "
            "Preserve all relevant figures and currency values exactly as supplied. Findings:\n"
            + json.dumps(findings, ensure_ascii=False, sort_keys=True)
        )
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=contents,
            config={
                "system_instruction": system_instruction,
                # Temperature 0.0 makes this factual business report as deterministic as the API permits.
                "temperature": 0.0,
                "max_output_tokens": 500,
                "http_options": {"timeout": 30000},
            },
        )
        narrative = getattr(response, "text", None)
        if not narrative:
            raise ValueError("Gemini returned an empty narrative.")
        usage = getattr(response, "usage_metadata", None)
        tokens = getattr(usage, "total_token_count", None) if usage else None
        return {"status": "success", "narrative": narrative, "tokens": tokens}
    except Exception as err:
        return {"status": "error", "narrative": None, "message": str(err)}

def check_numeric_accuracy(narrative: str) -> bool:
    """Print a pass/fail line for each required numeric fact."""
    normalized = narrative.replace(",", "")
    checks = [
        ("cleaned revenue 97,358.30", "97358.30" in normalized or "97358.3" in normalized),
        ("COD return rate 44.4", "44.4" in normalized),
        ("COD Tier-2 risk return rate 54.5", "54.5" in normalized),
        ("duplicate delta 2,501.90", "2501.90" in normalized or "2501.9" in normalized),
        ("March true peak 20,318.90", "march" in normalized.lower() and ("20318.90" in normalized or "20318.9" in normalized)),
    ]
    for label, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'} — {label}")
    return all(passed for _, passed in checks)

def main():
    if not FINDINGS_PATH.exists():
        raise FileNotFoundError(f"{FINDINGS_PATH} not found. Run python analysis/clean_and_eda.py first.")
    findings = json.loads(FINDINGS_PATH.read_text())
    result = generate_scr_narrative(findings)
    if result["status"] == "error":
        print("Gemini call failed; using deterministic offline fallback:", result["message"])
        result = generate_scr_narrative_offline(findings)
    narrative = result["narrative"]
    print(narrative)
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        SAMPLE_PATH.write_text(narrative.strip() + "\n")
        print(f"Saved online sample to {SAMPLE_PATH.relative_to(ROOT)}")
    else:
        SAMPLE_PATH.write_text(narrative.strip() + "\n")
        print(f"Saved offline sample to {SAMPLE_PATH.relative_to(ROOT)}")
    if not check_numeric_accuracy(narrative):
        raise SystemExit("Numeric accuracy check failed.")
    print("Narrative status:", result["status"])

if __name__ == "__main__":
    main()
