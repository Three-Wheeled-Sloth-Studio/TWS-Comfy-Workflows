param(
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host ""
    Write-Host "ComfyUI Music Video Model Installer"
    Write-Host ""
    Write-Host "Run from the ComfyUI root directory that contains the models folder."
    Write-Host ""
    Write-Host "The script writes only to relative paths under .\models\"
    Write-Host ""
    exit 0
}

$Models = Join-Path (Get-Location) "models"

if (-not (Test-Path $Models -PathType Container)) {
    Write-Error "No .\models directory was found. Run this tool from the ComfyUI root directory that contains the models folder."
}

if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    Write-Error "curl.exe was not found on PATH."
}

$Diffusion = Join-Path $Models "diffusion_models"
$TextEnc   = Join-Path $Models "text_encoders"
$VAE       = Join-Path $Models "vae"

$null = New-Item -ItemType Directory -Force -Path $Diffusion
$null = New-Item -ItemType Directory -Force -Path $TextEnc
$null = New-Item -ItemType Directory -Force -Path $VAE

function Download-Model {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$Url,
        [Parameter(Mandatory=$true)][string]$Destination
    )

    $Target = Join-Path $Destination $Name

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Model: $Name"
    Write-Host "Destination: $Target"
    Write-Host "============================================================"

    if (Test-Path $Target) {
        $Size = (Get-Item $Target).Length
        if ($Size -gt 1MB) {
            Write-Host "Already exists - skipping."
            return
        }
    }

    & curl.exe -L --fail --retry 5 --retry-delay 5 --continue-at - --output $Target $Url

    if ($LASTEXITCODE -ne 0) {
        throw "Download failed: $Name"
    }

    Write-Host "Finished: $Name"
}

Write-Host ""
Write-Host "ComfyUI root: $(Get-Location)"
Write-Host "Models root:  $Models"
Write-Host ""
Write-Host "Downloading music-video models..."

Download-Model -Name "z_image_turbo_bf16.safetensors" -Url "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors?download=true" -Destination $Diffusion
Download-Model -Name "qwen_3_4b.safetensors" -Url "https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors?download=true" -Destination $TextEnc
Download-Model -Name "ae.safetensors" -Url "https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/vae/ae.safetensors?download=true" -Destination $VAE
Download-Model -Name "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors" -Url "https://huggingface.co/Lightricks/LTX-2.5/resolve/main/diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors?download=true" -Destination $Diffusion
Download-Model -Name "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors" -Url "https://huggingface.co/Lightricks/LTX-2.5/resolve/main/text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors?download=true" -Destination $TextEnc
Download-Model -Name "ltx-2.5-video-vae-bf16.safetensors" -Url "https://huggingface.co/Lightricks/LTX-2.5/resolve/main/vae/ltx-2.5-video-vae-bf16.safetensors?download=true" -Destination $VAE
Download-Model -Name "ltx-2.5-audio-vae-bf16.safetensors" -Url "https://huggingface.co/Lightricks/LTX-2.5/resolve/main/vae/ltx-2.5-audio-vae-bf16.safetensors?download=true" -Destination $VAE

Write-Host ""
Write-Host "Downloads complete."
Write-Host ""
Write-Host "If the workflow references '*-control' LTX filenames, select these installed variants:"
Write-Host "  ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors"
Write-Host "  gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"
Write-Host ""
