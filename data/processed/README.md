# Clean groundwater import

`groundwater_required_columns.csv` is a derived, app-ready copy of the supplied Andhra Pradesh and Karnataka telemetry files.

Only these fields are retained:

- `station_name`
- `state`
- `district`
- `latitude`
- `longitude`
- `measured_at`
- `groundwater_level_m`
- `source_period`
- `source_file`

The original downloaded files are not modified. The groundwater level remains in metres exactly as supplied. It is historical/imported data and must not be described as a current ESP32 reading.
