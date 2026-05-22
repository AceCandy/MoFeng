$ErrorActionPreference = 'Stop'

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RootDir 'backend'
$FrontendDir = Join-Path $RootDir 'frontend'
$BackendHost = '0.0.0.0'
$BackendProxyHost = '127.0.0.1'
$BackendDefaultPort = 8000
$FrontendHost = '0.0.0.0'
$FrontendHmrHost = 'localhost'
$FrontendDefaultPort = 5173

if (-not (Test-Path $BackendDir) -or -not (Test-Path $FrontendDir)) {
    throw 'backend or frontend directory not found.'
}

$backendProcess = $null
$frontendProcess = $null
$BackendPython = $null
$npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    throw 'npm.cmd not found. Please install Node.js 18+.'
}

$taskkillExe = (Get-Command taskkill.exe -ErrorAction SilentlyContinue).Source

function Resolve-VenvPython {
    $candidates = @(
        (Join-Path $BackendDir '.venv\Scripts\python.exe'),
        (Join-Path $BackendDir '.venv\bin\python')
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Resolve-BootstrapPython {
    $venvPython = Resolve-VenvPython
    if ($venvPython) {
        return $venvPython
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    $python3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3) {
        return $python3.Source
    }

    throw 'Python 3.10+ not found.'
}

function Invoke-CheckedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList,
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage
    )

    Push-Location $WorkingDirectory
    try {
        & $FilePath @ArgumentList
        if ($LASTEXITCODE -ne 0) {
            throw $FailureMessage
        }
    }
    finally {
        Pop-Location
    }
}

function Ensure-FrontendDependencies {
    if (Test-Path (Join-Path $FrontendDir 'node_modules')) {
        return
    }

    Write-Host 'frontend/node_modules not found, running npm install...'
    Invoke-CheckedProcess -FilePath $npmCmd.Source -ArgumentList @('install') -WorkingDirectory $FrontendDir -FailureMessage 'npm install failed.'
}

function Ensure-BackendEnvironment {
    $bootstrapPython = Resolve-BootstrapPython
    $requirementsFile = Join-Path $BackendDir 'requirements.txt'

    if (-not (Test-Path (Join-Path $BackendDir '.venv'))) {
        Write-Host 'backend/.venv not found, creating virtual environment...'
        Invoke-CheckedProcess -FilePath $bootstrapPython -ArgumentList @('-m', 'venv', (Join-Path $BackendDir '.venv')) -WorkingDirectory $RootDir -FailureMessage 'Failed to create backend virtual environment.'
    }

    $script:BackendPython = Resolve-VenvPython
    if (-not $script:BackendPython) {
        $script:BackendPython = $bootstrapPython
    }

    & $script:BackendPython -c "import uvicorn" *> $null
    if ($LASTEXITCODE -eq 0) {
        return
    }

    if (-not (Test-Path $requirementsFile)) {
        throw 'backend/requirements.txt not found. Cannot install backend dependencies automatically.'
    }

    Write-Host 'Current Python environment is missing uvicorn, installing backend requirements...'
    Invoke-CheckedProcess -FilePath $script:BackendPython -ArgumentList @('-m', 'pip', 'install', '-r', $requirementsFile) -WorkingDirectory $BackendDir -FailureMessage 'Backend dependency installation failed.'
}

function Test-PortAvailable {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BindHost,
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $listener = $null
    try {
        $address = [System.Net.IPAddress]::Parse($BindHost)
        $listener = [System.Net.Sockets.TcpListener]::new($address, $Port)
        $listener.Start()
        return $true
    }
    catch [System.Net.Sockets.SocketException] {
        return $false
    }
    finally {
        if ($listener) {
            $listener.Stop()
        }
    }
}

function Find-AvailablePort {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BindHost,
        [Parameter(Mandatory = $true)]
        [int]$StartPort
    )

    for ($port = $StartPort; $port -le 65535; $port++) {
        if (Test-PortAvailable -BindHost $BindHost -Port $port) {
            return $port
        }
    }

    throw "No available port found in range ${BindHost}:${StartPort}-65535."
}

function Stop-TrackedProcess {
    param([System.Diagnostics.Process]$Process)

    if (-not $Process) {
        return
    }

    try {
        if ($Process.HasExited) {
            return
        }
    }
    catch {
        return
    }

    if ($taskkillExe) {
        & $taskkillExe /PID $Process.Id /T /F *> $null
        return
    }

    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
}

try {
    Ensure-FrontendDependencies
    Ensure-BackendEnvironment

    $BackendPort = Find-AvailablePort -BindHost $BackendHost -StartPort $BackendDefaultPort
    $FrontendPort = Find-AvailablePort -BindHost $FrontendHost -StartPort $FrontendDefaultPort

    if ($BackendPort -ne $BackendDefaultPort) {
        Write-Host "Detected backend default port $BackendDefaultPort in use, switching to $BackendPort."
    }

    if ($FrontendPort -ne $FrontendDefaultPort) {
        Write-Host "Detected frontend default port $FrontendDefaultPort in use, switching to $FrontendPort."
    }

    if (-not (Test-Path (Join-Path $BackendDir '.env')) -and (Test-Path (Join-Path $BackendDir 'env.example'))) {
        Write-Host 'Hint: backend/.env not found. You can create it from backend/env.example.' -ForegroundColor Yellow
    }

    Write-Host 'Starting backend dev server...'
    $backendProcess = Start-Process -FilePath $BackendPython -ArgumentList '-m', 'uvicorn', 'app.main:app', '--reload', '--host', $BackendHost, '--port', $BackendPort -WorkingDirectory $BackendDir -PassThru

    $previousFrontendEnv = @{
        BACKEND_PROXY_HOST = $env:BACKEND_PROXY_HOST
        BACKEND_PORT = $env:BACKEND_PORT
        FRONTEND_HOST = $env:FRONTEND_HOST
        FRONTEND_PORT = $env:FRONTEND_PORT
        FRONTEND_HMR_HOST = $env:FRONTEND_HMR_HOST
    }

    Write-Host 'Starting frontend dev server...'
    try {
        # 前端 dev server 从环境变量读取代理和监听配置，子进程会继承这里设置的值。
        $env:BACKEND_PROXY_HOST = $BackendProxyHost
        $env:BACKEND_PORT = $BackendPort
        $env:FRONTEND_HOST = $FrontendHost
        $env:FRONTEND_PORT = $FrontendPort
        $env:FRONTEND_HMR_HOST = $FrontendHmrHost

        $frontendProcess = Start-Process -FilePath $npmCmd.Source -ArgumentList 'run', 'dev' -WorkingDirectory $FrontendDir -PassThru
    }
    finally {
        foreach ($entry in $previousFrontendEnv.GetEnumerator()) {
            if ($null -eq $entry.Value) {
                Remove-Item -Path "Env:\$($entry.Key)" -ErrorAction SilentlyContinue
            }
            else {
                Set-Item -Path "Env:\$($entry.Key)" -Value $entry.Value
            }
        }
    }

    Write-Host ''
    Write-Host 'Dev environment started:'
    Write-Host "- Backend listen address: http://$BackendHost`:$BackendPort"
    Write-Host "- Frontend listen address: http://$FrontendHost`:$FrontendPort"
    Write-Host "- Local frontend: http://127.0.0.1:$FrontendPort"
    Write-Host "- Local API proxy: http://$BackendProxyHost`:$BackendPort/api"
    Write-Host 'Closing this window will try to stop both processes.'
    Write-Host ''

    while ($true) {
        Start-Sleep -Seconds 1
        if ($backendProcess.HasExited -or $frontendProcess.HasExited) {
            break
        }
    }
}
finally {
    Stop-TrackedProcess -Process $backendProcess
    Stop-TrackedProcess -Process $frontendProcess
}
