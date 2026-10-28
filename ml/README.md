# HydroInsight model training

The quality pipeline uses the two CGWB chemistry CSVs as sources. The original TabNet script cannot run against these files because:

- `WQI_Class` is not present in either CSV.
- The configured feature names do not match the headers.
- Temperature and turbidity are not measured in these files.
- TDS is present in only about 14–18% of rows.

`train_quality_model.py` creates a reproducible screening target using a weighted-arithmetic WQI formula over five observed inputs: pH, EC, TDS, total hardness, and chloride. It compares logistic regression, random forest, ExtraTrees, and XGBoost using stratified five-fold macro-F1. The best candidate is refit on all complete rows and saved with its feature order, classes, units, limits, source mapping, and metrics.

Example:

```powershell
python ml/train_quality_model.py `
  --output-dir ml/artifacts `
  "C:\Users\Acer\Downloads\gwq_chemical_parameter_manual_cgwb_ka_1961_2025.csv" `
  "C:\Users\Acer\Downloads\gwq_chemical_parameter_manual_cgwb_ap_1961_2025.csv"
```

The model is a screening classifier trained on formula-derived labels. It must not be presented as a laboratory or potability certification.
