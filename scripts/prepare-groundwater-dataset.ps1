param(
  [string]$Output = "data/processed/groundwater_required_columns.csv",
  [int]$MaxRowsPerFile = 5000
)

$inputs = @(
  @{ Path = 'C:\Users\Acer\Downloads\gwl_tel_6_hourly_andhra-pradesh-gw_ap_1991_2020.csv'; Period = '1991-2020' },
  @{ Path = 'C:\Users\Acer\Downloads\gwl_tel_6_hourly_andhra_pradesh_gw_ap_2021_2025.csv'; Period = '2021-2025' },
  @{ Path = 'C:\Users\Acer\Downloads\gwl_tel_6_hourly_andhra_pradesh_gw_ap_2026_2030.csv'; Period = '2026-2030' },
  @{ Path = 'C:\Users\Acer\Downloads\gwl_tel_6_hourly_karnataka_ka_2021_2025.csv'; Period = '2021-2025' },
  @{ Path = 'C:\Users\Acer\Downloads\gwl_tel_6_hourly_karnataka_ka_2026_2030.csv'; Period = '2026-2030' }
)

$rows = foreach ($input in $inputs) {
  if (-not (Test-Path -LiteralPath $input.Path)) { continue }
  $source = Split-Path -Leaf $input.Path
  $data = Import-Csv -LiteralPath $input.Path | Select-Object -First $MaxRowsPerFile
  foreach ($row in $data) {
    $levelColumn = @($row.PSObject.Properties.Name | Where-Object { $_ -match '^Groundwater Level' }) | Select-Object -First 1
    if (-not $levelColumn) { continue }
    $level = 0.0
    $latitude = 0.0
    $longitude = 0.0
    if (-not [double]::TryParse(([string]$row.$levelColumn).Replace(',', '').Trim(), [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$level)) { continue }
    if (-not [double]::TryParse(([string]$row.Latitude).Trim(), [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$latitude)) { continue }
    if (-not [double]::TryParse(([string]$row.Longitude).Trim(), [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$longitude)) { continue }
    if ([string]::IsNullOrWhiteSpace($row.Station) -or ($latitude -eq 0 -and $longitude -eq 0)) { continue }
    [pscustomobject]@{
      station_name = ([string]$row.Station).Trim()
      state = ([string]$row.State).Trim()
      district = ([string]$row.District).Trim()
      latitude = $latitude
      longitude = $longitude
      measured_at = ([string]$row.'Data Acquisition Time').Trim()
      groundwater_level_m = $level
      source_period = $input.Period
      source_file = $source
    }
  }
}

$parent = Split-Path -Parent $Output
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$rows | Export-Csv -LiteralPath $Output -NoTypeInformation -Encoding UTF8
Write-Output "Created $Output with $(@($rows).Count) rows and $(@($rows | Group-Object station_name).Count) stations."
