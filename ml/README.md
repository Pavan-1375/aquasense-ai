# HydroInsight model training

The quality pipeline uses the two CGWB chemistry CSVs as sources. The original TabNet script cannot run against these files because:

- `WQI_Class` is not present in either CSV.
- The configured feature names do not match the headers.
- Temperature and turbidity are not measured in these files.
- TDS is present in only about 14–18% of rows.

`train_quality_model.py` defines the active four-input contract: pH, TDS, turbidity and temperature. The supplied CGWB chemistry files are not compatible because they do not contain turbidity and temperature. Do not train this script against those files unless a compatible dataset is supplied.

Example:

```powershell
python ml/train_quality_model.py `
  --output-dir ml/artifacts `
  "C:\Users\Acer\Downloads\gwq_chemical_parameter_manual_cgwb_ka_1961_2025.csv" `
  "C:\Users\Acer\Downloads\gwq_chemical_parameter_manual_cgwb_ap_1961_2025.csv"
```

The active artifact is an Extra Trees screening classifier trained on 300 compatible four-parameter records. Its labels are formula-derived, not laboratory-derived. Report the model as screening support, never as laboratory agreement or potability certification. The backend records the model version as `extra-trees-four-parameter-0.2`.
