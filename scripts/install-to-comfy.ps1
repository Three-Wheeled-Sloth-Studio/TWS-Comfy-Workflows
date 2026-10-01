[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyRoot,
    [switch]$InstallModels
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$resolvedRepoRoot = [System.IO.Path]::GetFullPath($repoRoot)
$resolvedComfyRoot = [System.IO.Path]::GetFullPath($ComfyRoot)

if (-not (Test-Path -LiteralPath $resolvedComfyRoot -PathType Container)) {
    throw "ComfyUI root does not exist: $resolvedComfyRoot"
}

$copies = @(
    @{
        Source = Join-Path $resolvedRepoRoot 'custom_nodes\comfyui_audio_duration_plan'
        Destination = Join-Path $resolvedComfyRoot 'custom_nodes\comfyui_audio_duration_plan'
        Directory = $true
    },
    @{
        Source = Join-Path $resolvedRepoRoot 'user\default\workflows\video_wan2_2_14B_s2v.json'
        Destination = Join-Path $resolvedComfyRoot 'user\default\workflows\video_wan2_2_14B_s2v.json'
        Directory = $false
    },
    @{
        Source = Join-Path $resolvedRepoRoot 'user\default\workflows\video_wan2_2_14B_s2v_auto_duration.json'
        Destination = Join-Path $resolvedComfyRoot 'user\default\workflows\video_wan2_2_14B_s2v_auto_duration.json'
        Directory = $false
    },
    @{
        Source = Join-Path $resolvedRepoRoot 'user\default\workflows\video_wan2_2_14B_s2v_auto_duration_windowed.json'
        Destination = Join-Path $resolvedComfyRoot 'user\default\workflows\video_wan2_2_14B_s2v_auto_duration_windowed.json'
        Directory = $false
    },
    @{
        Source = Join-Path $resolvedRepoRoot 'user\default\workflows\video_wan2_2_14B_s2v_motion_loop.json'
        Destination = Join-Path $resolvedComfyRoot 'user\default\workflows\video_wan2_2_14B_s2v_motion_loop.json'
        Directory = $false
    },
    @{
        Source = Join-Path $resolvedRepoRoot 'user\default\workflows\video_wan2_2_14B_s2v_motion_poster_guided.json'
        Destination = Join-Path $resolvedComfyRoot 'user\default\workflows\video_wan2_2_14B_s2v_motion_poster_guided.json'
        Directory = $false
    }
)

foreach ($copy in $copies) {
    if (-not (Test-Path -LiteralPath $copy.Source)) {
        throw "Repository source is missing: $($copy.Source)"
    }
    if ([System.IO.Path]::GetFullPath($copy.Source) -eq [System.IO.Path]::GetFullPath($copy.Destination)) {
        Write-Host "Already in place: $($copy.Destination)"
        continue
    }
    if ($PSCmdlet.ShouldProcess($copy.Destination, "Install project file")) {
        $parent = Split-Path -Parent $copy.Destination
        $null = New-Item -ItemType Directory -Path $parent -Force
        if ($copy.Directory) {
            Copy-Item -LiteralPath $copy.Source -Destination $parent -Recurse -Force
        } else {
            Copy-Item -LiteralPath $copy.Source -Destination $copy.Destination -Force
        }
    }
}

if ($InstallModels) {
    & (Join-Path $PSScriptRoot 'install-wan-s2v-assets.ps1') -ComfyRoot $resolvedComfyRoot
}

Write-Host 'Installation complete. Restart ComfyUI to load or refresh custom nodes.'
