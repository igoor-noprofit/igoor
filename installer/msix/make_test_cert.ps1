# Creates the self-signed certificate used to sign the local-test MSIX.
# The certificate subject MUST match the Publisher in AppxManifest.xml exactly
# (default: the Partner Center Publisher ID). Prints THUMBPRINT=... on success.
# Run: powershell -NoProfile -ExecutionPolicy Bypass -File make_test_cert.ps1 [-Subject 'CN=...']

param([string]$Subject = 'CN=AFF811DC-40E0-4A1D-A8C8-AA38A5208E53')

$existing = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -eq $Subject }
if ($existing) { $existing | Remove-Item }

$cert = New-SelfSignedCertificate -Type Custom -Subject $Subject `
    -KeyUsage DigitalSignature -FriendlyName 'IGOOR MSIX Test Signing' `
    -CertStoreLocation 'Cert:\CurrentUser\My' `
    -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3', '2.5.29.19={text}')

Export-Certificate -Cert $cert -FilePath "$PSScriptRoot\IGOORMsixTest.cer" | Out-Null
Write-Output ('THUMBPRINT=' + $cert.Thumbprint)
