[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyRoot,
    [switch]$ListOnly
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $repoRoot 'assets\wan-s2v-models.json'
$resolvedComfyRoot = [System.IO.Path]::GetFullPath($ComfyRoot)

if (-not (Test-Path -LiteralPath $resolvedComfyRoot -PathType Container)) {
    throw "ComfyUI root does not exist: $resolvedComfyRoot"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($model in $manifest.models) {
    $destinationDirectory = Join-Path $resolvedComfyRoot ($model.destination -replace '/', '\')
    $destination = Join-Path $destinationDirectory $model.name
    Write-Host ("{0} -> {1}" -f $model.url, $destination)

    if ($ListOnly) {
        continue
    }

    if (Test-Path -LiteralPath $destination -PathType Leaf) {
        Write-Host "Already present: $destination"
        continue
    }

    if ($PSCmdlet.ShouldProcess($destination, "Download model")) {
        $null = New-Item -ItemType Directory -Path $destinationDirectory -Force
        $partial = "$destination.partial"
        & curl.exe -L --fail --retry 5 --retry-delay 5 -C - --output $partial $model.url
        if ($LASTEXITCODE -ne 0) {
            throw "Download failed: $($model.name)"
        }
        Move-Item -LiteralPath $partial -Destination $destination -Force
    }
}
