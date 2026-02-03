$content = Get-Content "version.py"
$match = $content | Select-String "__version__"
if ($match) {
    $version = ($match -split "=")[1].Trim().Replace("`"", "").Replace("'", "").Trim()
    Write-Output $version
}
