param(
    [string]$Target,

    [string]$Host,

    [string]$User,

    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [string]$ExpectedSha,

    [int]$Port = 22,

    [string]$RemoteCompose = "/opt/tg-bot/compose.yaml",

    [string]$NginxService = "nginx",

    [string]$LocalNginxConf = (Join-Path (Split-Path $PSScriptRoot -Parent) "nginx/nginx.conf"),

    [string]$RemoteNginxConf = "/etc/nginx/nginx.conf",

    [switch]$SkipNginxConf,

    [switch]$SkipHttp,

    [string[]]$HttpEndpoint,

    [int]$MaxRedirects = 10,

    [int]$HttpTimeout = 10,

    [string]$Identity,

    [string[]]$SshOption
)

if (-not $Target -and (-not $Host -or -not $User)) {
    Write-Error "Specify either -Target (SSH config alias) or both -Host and -User."
    exit 1
}

if (-not $ExpectedSha) {
    $gitResult = git rev-parse HEAD 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Unable to derive git SHA. Provide --ExpectedSha explicitly."
        exit 1
    }
    $ExpectedSha = $gitResult.Trim()
}

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $pythonCmd) {
    Write-Error "Python interpreter not found. Ensure 'python' (or 'py') is available in PATH."
    exit 1
}

$python = $pythonCmd.Path
$scriptPath = Join-Path $PSScriptRoot "verify_deploy.py"

if (-not (Test-Path -Path $scriptPath)) {
    Write-Error "verify_deploy.py not found at $scriptPath"
    exit 1
}

$argsList = @(
    "--base-url", $BaseUrl,
    "--expected-sha", $ExpectedSha,
    "--remote-compose", $RemoteCompose,
    "--nginx-service", $NginxService,
    "--local-nginx-conf", $LocalNginxConf,
    "--remote-nginx-conf", $RemoteNginxConf,
    "--max-redirects", $MaxRedirects.ToString(),
    "--http-timeout", $HttpTimeout.ToString()
)

if ($Target) {
    $argsList += @("--ssh-target", $Target)
} else {
    $argsList += @("--host", $Host, "--user", $User, "--port", $Port.ToString())
}

if ($SkipNginxConf) {
    $argsList += "--skip-nginx-conf"
}

if ($SkipHttp) {
    $argsList += "--skip-http"
}

if ($HttpEndpoint) {
    foreach ($endpoint in $HttpEndpoint) {
        if ($null -ne $endpoint -and $endpoint -ne "") {
            $argsList += @("--http-endpoint", $endpoint)
        }
    }
}

if ($Identity) {
    $argsList += @("--identity", $Identity)
}

if ($SshOption) {
    foreach ($option in $SshOption) {
        if ($null -ne $option -and $option -ne "") {
            $argsList += @("--ssh-option", $option)
        }
    }
}

& $python $scriptPath @argsList
exit $LASTEXITCODE
