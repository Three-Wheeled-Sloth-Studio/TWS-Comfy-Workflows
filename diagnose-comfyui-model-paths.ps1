param([switch]$Help)
$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Diagnose whether a ComfyUI installation can see the seven music-video models."
    Write-Host "Run from the ComfyUI root where the models were installed."
    exit 0
}

$Root = (Get-Location).Path
$Models = Join-Path $Root "models"
if (-not (Test-Path $Models -PathType Container)) {
    throw "No .\models directory found. Run from the ComfyUI root where the models were installed."
}

$Expected = [ordered]@{
    "diffusion_models/z_image_turbo_bf16.safetensors" = "diffusion_models"
    "text_encoders/qwen_3_4b.safetensors" = "text_encoders"
    "vae/ae.safetensors" = "vae"
    "diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors" = "diffusion_models"
    "text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors" = "text_encoders"
    "vae/ltx-2.5-video-vae-bf16.safetensors" = "vae"
    "vae/ltx-2.5-audio-vae-bf16.safetensors" = "vae"
}

Write-Host ""
Write-Host "Installed-model root: $Models"
$MissingLocal = @()
foreach ($Rel in $Expected.Keys) {
    $Path = Join-Path $Models ($Rel -replace '/', '\')
    if (Test-Path $Path -PathType Leaf) {
        $GB = [math]::Round((Get-Item $Path).Length / 1GB, 2)
        Write-Host "  FOUND  $Rel ($GB GB)"
    } else {
        Write-Host "  MISSING $Rel"
        $MissingLocal += $Rel
    }
}

Write-Host ""
Write-Host "Searching for ComfyUI model-path configuration..."
$ConfigCandidates = @(
    (Join-Path $Root "extra_model_paths.yaml"),
    (Join-Path $Root "extra_model_paths.yml"),
    (Join-Path $env:APPDATA "ComfyUI\extra_model_paths.yaml"),
    (Join-Path $env:APPDATA "ComfyUI\extra_model_paths.yml"),
    (Join-Path $env:LOCALAPPDATA "ComfyUI\extra_model_paths.yaml"),
    (Join-Path $env:LOCALAPPDATA "ComfyUI\extra_model_paths.yml")
) | Select-Object -Unique

$FoundConfigs = @($ConfigCandidates | Where-Object { Test-Path $_ -PathType Leaf })
if ($FoundConfigs.Count -eq 0) {
    Write-Host "  No extra_model_paths YAML found in the checked locations."
} else {
    foreach ($Cfg in $FoundConfigs) {
        Write-Host "  CONFIG $Cfg"
        Get-Content $Cfg | ForEach-Object { Write-Host "    $_" }
    }
}

Write-Host ""
Write-Host "Searching likely ComfyUI Desktop locations for alternate model roots..."
$SearchRoots = @(
    (Join-Path $env:APPDATA "ComfyUI"),
    (Join-Path $env:LOCALAPPDATA "ComfyUI"),
    (Join-Path $env:USERPROFILE "ComfyUI"),
    (Join-Path $env:USERPROFILE "Documents\ComfyUI")
) | Select-Object -Unique

$ModelRoots = @()
foreach ($Base in $SearchRoots) {
    if (Test-Path $Base -PathType Container) {
        $Dirs = @(Get-ChildItem -Path $Base -Directory -Filter "models" -Recurse -Depth 4 -ErrorAction SilentlyContinue)
        foreach ($Dir in $Dirs) {
            if ($ModelRoots -notcontains $Dir.FullName) { $ModelRoots += $Dir.FullName }
        }
    }
}
if ($ModelRoots -notcontains $Models) { $ModelRoots += $Models }

foreach ($MR in $ModelRoots) {
    $Count = 0
    foreach ($Rel in $Expected.Keys) {
        if (Test-Path (Join-Path $MR ($Rel -replace '/', '\')) -PathType Leaf) { $Count++ }
    }
    Write-Host "  MODEL ROOT [$Count/7] $MR"
}

Write-Host ""
if ($MissingLocal.Count -gt 0) {
    Write-Host "RESULT: The intended installation root itself is missing $($MissingLocal.Count) model(s)."
    exit 2
}

Write-Host "RESULT: All seven model files exist in the intended installation root."
Write-Host "If ComfyUI still reports all seven missing, its running backend is not indexing this root or has not refreshed since installation."
Write-Host ""
Write-Host "Recommended next action:"
Write-Host "  1. Fully exit ComfyUI Desktop, including its backend process."
Write-Host "  2. Restart it and reload the local workflow."
Write-Host "  3. If models remain missing, send the complete output of this diagnostic; it identifies alternate roots/configuration without copying models."
