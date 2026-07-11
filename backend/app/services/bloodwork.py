"""Reference ranges for common blood markers.

Used to prefill units and ranges in the entry form; the range in force is
copied onto each blood_results row so history stays stable if these change.
Ranges are typical adult reference intervals — labs vary; users should prefer
the range printed on their own lab report.
"""

MARKER_REFERENCE: dict[str, dict] = {
    # lipids
    "Total Cholesterol": {"unit": "mmol/L", "low": None, "high": 5.0, "group": "Lipids"},
    "LDL Cholesterol": {"unit": "mmol/L", "low": None, "high": 3.0, "group": "Lipids"},
    "HDL Cholesterol": {"unit": "mmol/L", "low": 1.0, "high": None, "group": "Lipids"},
    "Triglycerides": {"unit": "mmol/L", "low": None, "high": 1.7, "group": "Lipids"},
    # metabolic
    "Fasting Glucose": {"unit": "mmol/L", "low": 3.9, "high": 5.6, "group": "Metabolic"},
    "HbA1c": {"unit": "mmol/mol", "low": 20, "high": 42, "group": "Metabolic"},
    "Creatinine": {"unit": "µmol/L", "low": 60, "high": 110, "group": "Metabolic"},
    "eGFR": {"unit": "mL/min/1.73m²", "low": 90, "high": None, "group": "Metabolic"},
    "ALT": {"unit": "U/L", "low": None, "high": 41, "group": "Metabolic"},
    "AST": {"unit": "U/L", "low": None, "high": 40, "group": "Metabolic"},
    "Sodium": {"unit": "mmol/L", "low": 135, "high": 145, "group": "Metabolic"},
    "Potassium": {"unit": "mmol/L", "low": 3.5, "high": 5.1, "group": "Metabolic"},
    # CBC
    "Hemoglobin": {"unit": "g/L", "low": 130, "high": 175, "group": "Blood count"},
    "Hematocrit": {"unit": "%", "low": 40, "high": 52, "group": "Blood count"},
    "WBC": {"unit": "10⁹/L", "low": 4.0, "high": 11.0, "group": "Blood count"},
    "RBC": {"unit": "10¹²/L", "low": 4.5, "high": 5.9, "group": "Blood count"},
    "Platelets": {"unit": "10⁹/L", "low": 150, "high": 400, "group": "Blood count"},
    "Ferritin": {"unit": "µg/L", "low": 30, "high": 400, "group": "Blood count"},
    "Iron": {"unit": "µmol/L", "low": 10, "high": 30, "group": "Blood count"},
    # thyroid
    "TSH": {"unit": "mIU/L", "low": 0.4, "high": 4.0, "group": "Thyroid"},
    "Free T4": {"unit": "pmol/L", "low": 12, "high": 22, "group": "Thyroid"},
    # vitamins & minerals
    "Vitamin D (25-OH)": {"unit": "nmol/L", "low": 50, "high": 125, "group": "Vitamins"},
    "Vitamin B12": {"unit": "pmol/L", "low": 150, "high": 660, "group": "Vitamins"},
    "Folate": {"unit": "nmol/L", "low": 10, "high": 45, "group": "Vitamins"},
    "Magnesium": {"unit": "mmol/L", "low": 0.7, "high": 1.0, "group": "Vitamins"},
    # hormones
    "Total Testosterone": {"unit": "nmol/L", "low": 10, "high": 35, "group": "Hormones"},
    "Cortisol (morning)": {"unit": "nmol/L", "low": 140, "high": 690, "group": "Hormones"},
    "CRP": {"unit": "mg/L", "low": None, "high": 5.0, "group": "Inflammation"},
}


def catalogue() -> list[dict]:
    return [
        {"marker": name, **ref} for name, ref in MARKER_REFERENCE.items()
    ]


def out_of_range(value: float, low: float | None, high: float | None) -> str | None:
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return None
