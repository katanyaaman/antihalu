$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
if (Test-Path "$root\.venv\Scripts\python.exe") {
    & "$root\.venv\Scripts\python.exe" "$root\dashboard.py" @args
} else {
    python "$root\dashboard.py" @args
}
