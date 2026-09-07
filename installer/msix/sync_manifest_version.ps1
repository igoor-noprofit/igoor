# Sets the Identity Version in an AppxManifest.xml via the XML DOM.
# Called by build_msix.bat so the package version always matches version.py.
# Using the DOM (not regex) makes it immune to cmd quoting/anchoring issues
# that twice rewrote MinVersion by mistake.
#
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File sync_manifest_version.ps1 -Manifest <path> -Version <1.2.3.4>

param([Parameter(Mandatory = $true)][string]$Manifest,
      [Parameter(Mandatory = $true)][string]$Version)

$xml = New-Object System.Xml.XmlDocument
$xml.PreserveWhitespace = $true
$xml.Load($Manifest)
$xml.Package.Identity.Version = $Version
$xml.Save($Manifest)
Write-Output ("Identity Version set to " + $Version)
