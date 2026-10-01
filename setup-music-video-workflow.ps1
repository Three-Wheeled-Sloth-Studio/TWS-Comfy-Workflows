param([switch]$Help)
$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Run from the ComfyUI root directory containing .\models."
    Write-Host "Installs/verifies models, fetches the canonical workflow, preserves an upstream copy, and creates a locally compatible copy."
    exit 0
}

if (-not (Test-Path ".\models" -PathType Container)) {
    throw "No .\models directory found. Run this tool from the ComfyUI root."
}

$ToolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Installer = Join-Path $ToolDir "install-music-video-models.ps1"
if (-not (Test-Path $Installer -PathType Leaf)) { throw "Model installer not found: $Installer" }

Write-Host ""
Write-Host "Step 1/3 - Install or verify required models"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Installer
if ($LASTEXITCODE -ne 0) { throw "Model installation/verification failed." }

$WorkflowDir = ".\user\default\workflows\tws-music-video"
$SourcePath = Join-Path $WorkflowDir "music_video_ALL_IN_ONE.upstream.json"
$PatchedPath = Join-Path $WorkflowDir "music_video_ALL_IN_ONE.local.json"
$SourceUrl = "https://raw.githubusercontent.com/GeekatplayStudio/ComfyUI-Music-to-Video/main/example_workflows/music_video_ALL_IN_ONE.json"
$null = New-Item -ItemType Directory -Force -Path $WorkflowDir

Write-Host ""
Write-Host "Step 2/3 - Fetch current upstream workflow"
& curl.exe -L --fail --retry 5 --retry-connrefused --retry-delay 3 --output $SourcePath $SourceUrl
if ($LASTEXITCODE -ne 0) { throw "Could not download the canonical music-video workflow." }

try {
    $Workflow = Get-Content -Raw -Path $SourcePath | ConvertFrom-Json
} catch {
    throw "Downloaded workflow is not valid JSON: $SourcePath"
}

Write-Host ""
Write-Host "Step 3/3 - Create and validate local workflow copy"
$Raw = Get-Content -Raw -Path $SourcePath
$PatchMap = [ordered]@{
    "ltx-2.5-22b-distilled-transformer-comfy-int8-control.safetensors" = "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors"
    "gemma4-12b-with-proj-ltx-2.5-comfy-int8-control.safetensors" = "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"
}
$PatchCount = 0
foreach ($Old in $PatchMap.Keys) {
    $New = $PatchMap[$Old]
    $Count = ([regex]::Matches($Raw, [regex]::Escape($Old))).Count
    if ($Count -gt 0) {
        $Raw = $Raw.Replace($Old, $New)
        $PatchCount += $Count
        Write-Host "Patched $Count reference(s): $Old -> $New"
    }
}
$Raw | Set-Content -Path $PatchedPath -Encoding UTF8

try {
    $Patched = Get-Content -Raw -Path $PatchedPath | ConvertFrom-Json
} catch {
    throw "Generated local workflow is not valid JSON: $PatchedPath"
}

$ExpectedModels = @(
    ".\models\diffusion_models\z_image_turbo_bf16.safetensors",
    ".\models\text_encoders\qwen_3_4b.safetensors",
    ".\models\vae\ae.safetensors",
    ".\models\diffusion_models\ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
    ".\models\text_encoders\gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
    ".\models\vae\ltx-2.5-video-vae-bf16.safetensors",
    ".\models\vae\ltx-2.5-audio-vae-bf16.safetensors"
)
$Missing = @($ExpectedModels | Where-Object { -not (Test-Path $_ -PathType Leaf) })
if ($Missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Missing expected model files:"
    $Missing | ForEach-Object { Write-Host "  $_" }
    throw "Local workflow validation failed because required model files are missing."
}

Write-Host ""
if ($PatchCount -eq 0) {
    Write-Host "Upstream already uses the locally installed LTX model variants; no substitutions were necessary."
}
Write-Host "Source copy:  $SourcePath"
Write-Host "Local copy:   $PatchedPath"
Write-Host ""
Write-Host "Setup complete. Load the local copy in ComfyUI:"
Write-Host "  $PatchedPath"
