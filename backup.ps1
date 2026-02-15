#requires -version 5.1
param(
    # Project root (defaults to the script folder)
    [string]$ProjectDir = $(if ($PSScriptRoot) { $PSScriptRoot } else { "." }),
    # Archive name in the project root
    [string]$ZipName    = "ummanet-backup.zip",
    # Backup destination
    [string]$BackupDir  = (Join-Path $env:USERPROFILE "Backups\Ummanet")
)

$ErrorActionPreference = "Stop"

# Paths
$root  = (Resolve-Path -LiteralPath $ProjectDir).Path
$zip   = Join-Path $root $ZipName
$stage = Join-Path $env:TEMP ("pyproj_stage_" + [guid]::NewGuid().ToString("N"))

Write-Host "[1/5] Project: $root"
Write-Host "[1/5] Backup dir: $BackupDir"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
New-Item -ItemType Directory -Force -Path $stage | Out-Null

# Move existing archive to backups with timestamp (and -vN if needed)
if (Test-Path -LiteralPath $zip) {
    $timestamp = Get-Date -Format "yyyy-MM-dd-HH-mm"
    $baseName  = [IO.Path]::GetFileNameWithoutExtension($ZipName)
    $ext       = [IO.Path]::GetExtension($ZipName)

    $backupZip = Join-Path $BackupDir ("{0}-{1}{2}" -f $baseName, $timestamp, $ext)
    $i = 2
    while (Test-Path -LiteralPath $backupZip) {
        $backupZip = Join-Path $BackupDir ("{0}-{1}-v{2}{3}" -f $baseName, $timestamp, $i, $ext)
        $i++
    }
    Write-Host "[0] Existing archive found, moving to: $backupZip"
    Move-Item -LiteralPath $zip -Destination $backupZip
}

# Exclude non-source stuff (build artifacts, caches, VCS/IDE, envs, archives, logs, etc.)
$excludeDirs = @(
    # Node/Frontend
    'node_modules','dist','build','out','coverage','.next','.nuxt','.output',
    '.angular','.svelte-kit','.parcel-cache','.vite','.vercel','.turbo','.cache',
    '.pnp','.yarn','storybook-static',
    # Python
    'venv','.venv','env','.tox','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','.ipynb_checkpoints',
    # VCS/IDE
    '.git','.github','.gitlab','.hg','.svn','.idea','.vscode'
)

$excludeExts = @(
    # Python compiled
    '.pyc','.pyo','.pyd',
    # Native/binaries
    '.so','.dll','.exe',
    # Archives & logs
    '.zip','.7z','.rar','.tar','.gz','.tgz','.xz','.bz2','.zst','.log','.tmp','.bak',
    # Sourcemaps
    '.map'
)

$excludeNames = @('Thumbs.db','.DS_Store')

# Regex for excluding directories anywhere in the path (case-insensitive)
$dirPattern = '(?i)(\\|/)(' + (($excludeDirs | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')(\\|/)'
$dirRx      = [regex]::new($dirPattern, [System.Text.RegularExpressions.RegexOptions]::Compiled)

# Any hidden ".name" directory in the path
$dotDirRx   = [regex]::new('(\\|/)\.[^\\/]+(\\|/)', [System.Text.RegularExpressions.RegexOptions]::Compiled)

Write-Host "[2/5] Scan & filter files..."
$allFiles = Get-ChildItem -Path $root -Recurse -File -Force -ErrorAction SilentlyContinue
$files = $allFiles | Where-Object {
    $full = $_.FullName
    -not $dirRx.IsMatch($full) -and
    -not $dotDirRx.IsMatch($full) -and
    -not $excludeNames.Contains($_.Name) -and
    -not $excludeExts.Contains($_.Extension.ToLower())
}

if (-not $files -or $files.Count -eq 0) {
    Remove-Item -LiteralPath $stage -Recurse -Force
    throw "No files left after filtering. Adjust exclude lists."
}

Write-Host ("[3/5] Copy {0} files to stage..." -f $files.Count)

# Normalize root without trailing slash
if ($root.EndsWith('\') -or $root.EndsWith('/')) { $root = $root.TrimEnd('\','/') }

foreach ($f in $files) {
    $rel = $f.FullName.Substring($root.Length).TrimStart('\','/')
    $dst = Join-Path $stage $rel
    $dstDir = Split-Path $dst
    if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Force -Path $dstDir | Out-Null }
    Copy-Item -LiteralPath $f.FullName -Destination $dst -Force
}

Write-Host "[4/5] Create ZIP..."
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -Force
$zipSize = (Get-Item $zip).Length / 1MB

Write-Host ("[5/5] Done: {0} ({1:N2} MB)" -f $zip, $zipSize)

# Cleanup
Remove-Item -LiteralPath $stage -Recurse -Force
