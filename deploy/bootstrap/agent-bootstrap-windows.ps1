# HyperFileLens Agent enrollment bootstrap (Windows). Rendered by GET /enrollment/bootstrap.
$ErrorActionPreference = "Stop"

function Test-HflAdmin {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-HflBootstrapLog {
  param(
    [Parameter(Mandatory = $true)][string]$Level,
    [Parameter(Mandatory = $true)][string]$Message
  )
  $ts = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
  if ($Message -notmatch '[.!?]$') { $Message = "$Message." }
  Write-Host "[$ts] [$Level] $Message"
}

if (-not (Test-HflAdmin)) {
  Write-HflBootstrapLog "INFO " "Administrator privileges are required. Approve the UAC prompt to continue."
  $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath)
  $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $argList -Verb RunAs -PassThru -Wait
  if ($null -eq $proc) {
    Write-HflBootstrapLog "FAIL " "Elevation was cancelled or failed."
    exit 1
  }
  exit $proc.ExitCode
}

$env:HFL_ORG_KEY = "__HFL_ORG_KEY__"
$env:HFL_NODE_ROLE = "__HFL_NODE_ROLE__"
$env:HFL_NODE_TOKEN = "__HFL_NODE_TOKEN__"
$env:HFL_API_BASE = "__HFL_API_BASE__"
$env:HFL_WSS_URL = "__HFL_WSS_URL__"
$env:HFL_INSECURE_TLS = "__HFL_INSECURE_TLS__"

function Get-HflEnrollmentBinary {
  param(
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $true)][string]$OutFile
  )
  $skipCert = ($env:HFL_INSECURE_TLS -ne '0')

  if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
    $curlArgs = @('-fL', '-o', $OutFile, $Url)
    if ($skipCert) { $curlArgs = @('-k') + $curlArgs }
    & curl.exe @curlArgs
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $OutFile)) { return }
    Write-HflBootstrapLog "WARN " "curl download failed (exit $LASTEXITCODE). Trying PowerShell instead."
  }

  try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    if ($skipCert) {
      [Net.ServicePointManager]::ServerCertificateValidationCallback = { [bool]1 }
    }
    (New-Object Net.WebClient).DownloadFile($Url, $OutFile)
  }
  catch {
    Write-HflBootstrapLog "FAIL " "Failed to download the enrollment tool: $($_.Exception.Message)"
    throw
  }
}

$nativeArch = if ($env:PROCESSOR_ARCHITEW6432) {
  $env:PROCESSOR_ARCHITEW6432
}
else {
  $env:PROCESSOR_ARCHITECTURE
}
$archRel = switch ($nativeArch) {
  "AMD64" { "amd64"; break }
  "ARM64" {
    Write-HflBootstrapLog "FAIL " "Windows ARM64 is not supported by this release."
    exit 4
  }
  "x86" {
    Write-HflBootstrapLog "FAIL " "32-bit Windows is not supported by this release."
    exit 4
  }
  default {
    Write-HflBootstrapLog "FAIL " "Unsupported Windows architecture $nativeArch."
    exit 4
  }
}
$bin = Join-Path $env:TEMP ("hfl-enroll-" + [guid]::NewGuid().ToString("n") + ".exe")

$enrollUrl = "$($env:HFL_API_BASE)/media/enroll-bootstrap/hfl-enroll-windows-$archRel.exe"
$exitCode = 3
try {
  Get-HflEnrollmentBinary -Url $enrollUrl -OutFile $bin
  & $bin install @args
  $exitCode = $LASTEXITCODE
}
finally {
  if (Test-Path -LiteralPath $bin) {
    Remove-Item -Force -LiteralPath $bin -ErrorAction SilentlyContinue
  }
}
exit $exitCode
