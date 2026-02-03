$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$versionFilePath = Join-Path $scriptPath "version.py"

if (Test-Path $versionFilePath) {
    $content = Get-Content $versionFilePath
    $match = $content | Select-String "__version__"
    if ($match) {
        $version = ($match -split "=")[1].Trim().Replace("`"", "").Replace("'", "").Trim()
        $version = $version.Trim()
        $Host.UI.WriteErrorLine($version)
    }
} else {
    Write-Error "version.py not found at: $versionFilePath"
}
