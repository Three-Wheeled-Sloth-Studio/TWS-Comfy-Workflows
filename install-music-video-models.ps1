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
        $ExistingGB = [math]::Round($Size / 1GB, 2)
        Write-Host "Existing file found: $ExistingGB GB."
        Write-Host "Verifying completion with the remote server; partial files will resume."
    }

    # Large Hugging Face files can occasionally lose a TLS connection mid-transfer.
    # Retry the curl invocation so --continue-at - resumes the partial file.
    $MaxAttempts = 10
    for ($Attempt = 1; $Attempt -le $MaxAttempts; $Attempt++) {
        Write-Host "Download attempt $Attempt of $MaxAttempts..."

        & curl.exe -L --fail --retry 10 --retry-connrefused --retry-delay 5 --connect-timeout 30 --continue-at - --output $Target $Url

        if ($LASTEXITCODE -eq 0) {
            Write-Host "Finished: $Name"
            return
        }

        # curl exit 22 means the server returned HTTP 4xx/5xx. Retrying the same
        # unauthenticated request will not fix gated/auth failures such as 401.
        if ($LASTEXITCODE -eq 22) {
            throw "Server rejected the download for $Name. If this is a gated Hugging Face model, accept its license/access terms and use an authenticated download."
        }

        if ($Attempt -lt $MaxAttempts) {
            $PartialSize = if (Test-Path $Target) { (Get-Item $Target).Length } else { 0 }
            $PartialGB = [math]::Round($PartialSize / 1GB, 2)
            Write-Warning "Transfer interrupted. Partial file is $PartialGB GB. Retrying in 10 seconds and resuming from the existing file..."
            Start-Sleep -Seconds 10
        }
    }

    throw "Download failed after $MaxAttempts attempts: $Name"
}

function Ensure-HuggingFaceCli {
    if (Get-Command hf -ErrorAction SilentlyContinue) {
        return
    }

    # hf.exe may already be installed by pip --user but absent from inherited PATH.
    $RoamingPython = Join-Path $env:APPDATA "Python"
    $ExistingHf = Get-ChildItem -Path $RoamingPython -Filter "hf.exe" -File -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($ExistingHf) {
        $ScriptsDir = Split-Path -Parent $ExistingHf.FullName
        $env:PATH = "$ScriptsDir;$env:PATH"
        Write-Host "Found existing Hugging Face CLI: $($ExistingHf.FullName)"
        return
    }

    Write-Host ""
    Write-Host "Hugging Face CLI is required for gated LTX 2.5 models and was not found."
    Write-Host "Installing huggingface_hub for the current Windows user..."

    $Python = Get-Command py.exe -ErrorAction SilentlyContinue
    if (-not $Python) { $Python = Get-Command python.exe -ErrorAction SilentlyContinue }
    if (-not $Python) { $Python = Get-Command python -ErrorAction SilentlyContinue }

    if (-not $Python) {
        throw "Python was not found on PATH. Install Python 3, then rerun this installer."
    }

    & $Python.Source -m pip install --user "huggingface_hub"
    if ($LASTEXITCODE -ne 0) {
        throw "Automatic installation of huggingface_hub failed."
    }

    # pip --user installs console scripts beside the user site-packages tree.
    # Python's reported user-base is not reliable for every Windows Python layout,
    # so derive the Scripts directory from the actual user-site path first.
    $CandidateScriptDirs = @()

    $UserSite = (& $Python.Source -m site --user-site).Trim()
    if ($LASTEXITCODE -eq 0 -and $UserSite) {
        $CandidateScriptDirs += (Join-Path (Split-Path $UserSite -Parent) "Scripts")
    }

    $UserBase = (& $Python.Source -m site --user-base).Trim()
    if ($LASTEXITCODE -eq 0 -and $UserBase) {
        $CandidateScriptDirs += (Join-Path $UserBase "Scripts")
    }

    # Also inspect the current user's standard roaming Python Scripts locations.
    $CandidateScriptDirs += Get-ChildItem -Path (Join-Path $env:APPDATA "Python") -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName "Scripts" }

    foreach ($ScriptsDir in ($CandidateScriptDirs | Select-Object -Unique)) {
        if (Test-Path (Join-Path $ScriptsDir "hf.exe") -PathType Leaf) {
            if (($env:PATH -split ';') -notcontains $ScriptsDir) {
                $env:PATH = "$ScriptsDir;$env:PATH"
            }
            break
        }
    }

    if (-not (Get-Command hf -ErrorAction SilentlyContinue)) {
        throw "huggingface_hub installed successfully, but hf.exe could not be located automatically."
    }

    Write-Host "Hugging Face CLI installed and available in this session."
}

function Download-HuggingFaceModel {
    param(
        [Parameter(Mandatory=$true)][string]$Repo,
        [Parameter(Mandatory=$true)][string]$RemotePath,
        [Parameter(Mandatory=$true)][string]$Destination
    )

    Ensure-HuggingFaceCli

    $Name = Split-Path $RemotePath -Leaf
    $Target = Join-Path $Destination $Name

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Model: $Name"
    Write-Host "Destination: $Target"
    Write-Host "Source: $Repo/$RemotePath"
    Write-Host "============================================================"

    if (Test-Path $Target -PathType Leaf) {
        $Size = (Get-Item $Target).Length
        if ($Size -gt 1MB) {
            $ExistingGB = [math]::Round($Size / 1GB, 2)
            Write-Host "Existing LTX model found: $ExistingGB GB. Skipping download."
            return
        }
        Write-Warning "Existing LTX file is suspiciously small and will be replaced: $Target"
        Remove-Item -Force $Target
    }

    & hf auth whoami
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "This machine is not authenticated to Hugging Face."
        Write-Host "Starting Hugging Face login now..."
        & hf auth login
        if ($LASTEXITCODE -ne 0) {
            throw "Hugging Face authentication failed."
        }
        & hf auth whoami
        if ($LASTEXITCODE -ne 0) {
            throw "Hugging Face login completed but no authenticated account is available."
        }
    }

    # Download to a temporary staging directory because hf --local-dir preserves
    # the repository's subdirectory structure. Move only the requested model into
    # ComfyUI's flat model-category directory after a successful download.
    $StageRoot = Join-Path ".\models\.hf-stage" ([guid]::NewGuid().ToString("N"))
    try {
        $null = New-Item -ItemType Directory -Force -Path $StageRoot
        & hf download $Repo $RemotePath --local-dir $StageRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Authenticated Hugging Face download failed: $Name"
        }

        $StageFile = Join-Path $StageRoot $RemotePath
        if (-not (Test-Path $StageFile -PathType Leaf)) {
            throw "Hugging Face reported success but the expected staged file was not found: $StageFile"
        }

        Move-Item -Force -Path $StageFile -Destination $Target
        Write-Host "Finished: $Name"
    }
    finally {
        if (Test-Path $StageRoot) {
            Remove-Item -Recurse -Force $StageRoot
        }
    }
}

Write-Host ""
Write-Host "ComfyUI root: $(Get-Location)"
Write-Host "Models root:  $Models"
Write-Host ""
Write-Host "Downloading music-video models..."

Download-Model -Name "z_image_turbo_bf16.safetensors" -Url "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors?download=true" -Destination $Diffusion
Download-Model -Name "qwen_3_4b.safetensors" -Url "https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors?download=true" -Destination $TextEnc
Download-Model -Name "ae.safetensors" -Url "https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/vae/ae.safetensors?download=true" -Destination $VAE
Download-HuggingFaceModel -Repo "Lightricks/LTX-2.5" -RemotePath "diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors" -Destination $Diffusion
Download-HuggingFaceModel -Repo "Lightricks/LTX-2.5" -RemotePath "text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors" -Destination $TextEnc
Download-HuggingFaceModel -Repo "Lightricks/LTX-2.5" -RemotePath "vae/ltx-2.5-video-vae-bf16.safetensors" -Destination $VAE
Download-HuggingFaceModel -Repo "Lightricks/LTX-2.5" -RemotePath "vae/ltx-2.5-audio-vae-bf16.safetensors" -Destination $VAE

Write-Host ""
Write-Host "Downloads complete."
Write-Host ""
Write-Host "If the workflow references '*-control' LTX filenames, select these installed variants:"
Write-Host "  ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors"
Write-Host "  gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"
Write-Host ""
