# Instalador de Job Hunter para Windows.
#
# Uso (pegar en PowerShell):
#   irm https://raw.githubusercontent.com/ambrociocastanazag-ctrl/job-hunter/main/install.ps1 | iex
#
# Descarga el proyecto en %USERPROFILE%\JobHunter, instala Python 3.12 y las
# dependencias con uv (todo dentro de esa carpeta, sin tocar el resto del
# sistema ni el PATH) y crea el acceso directo "Job Hunter" en el escritorio
# y en el menu Inicio. Correrlo otra vez actualiza el codigo sin borrar los
# datos del usuario (data/, logs/, .env, config/settings.yaml, config/profile.yaml).
#
# Variables de entorno opcionales (pruebas):
#   JOBHUNTER_DIR          carpeta de instalacion (default %USERPROFILE%\JobHunter)
#   JOBHUNTER_SOURCE       carpeta local con el codigo, en vez de bajarlo de GitHub
#   JOBHUNTER_NO_SHORTCUT  1 = no crear accesos directos
#   JOBHUNTER_NO_LAUNCH    1 = no abrir Job Hunter al terminar

# Todo va dentro de un scriptblock: con `irm | iex` el script corre en la
# sesion del usuario, asi que nada de `exit` (cerraria su ventana) ni de
# variables o preferencias que se queden colgando al terminar.
& {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest es 10x mas lento con la barra
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

    $Repo = 'ambrociocastanazag-ctrl/job-hunter'
    $Branch = 'main'
    $UvUrl = 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip'
    $Port = 5000

    $InstallDir = if ($env:JOBHUNTER_DIR) { $env:JOBHUNTER_DIR } else { Join-Path $env:USERPROFILE 'JobHunter' }
    $Tools = Join-Path $InstallDir 'tools'
    $Uv = Join-Path $Tools 'uv.exe'
    $TmpDir = Join-Path ([IO.Path]::GetTempPath()) ("jobhunter-" + [guid]::NewGuid().ToString('N'))

    function Write-Step([string]$Message) {
        Write-Host ''
        Write-Host "==> $Message" -ForegroundColor Cyan
    }

    function Assert-ExitCode([string]$What) {
        if ($LASTEXITCODE -ne 0) { throw "$What fallo (codigo $LASTEXITCODE)." }
    }

    function Test-PortOpen([int]$PortNumber) {
        $client = New-Object Net.Sockets.TcpClient
        try {
            $async = $client.BeginConnect('127.0.0.1', $PortNumber, $null, $null)
            return ($async.AsyncWaitHandle.WaitOne(500) -and $client.Connected)
        } catch {
            return $false
        } finally {
            $client.Close()
        }
    }

    function New-Shortcut([string]$Path, [string]$Target, [string]$WorkDir, [string]$Icon) {
        $shell = New-Object -ComObject WScript.Shell
        $lnk = $shell.CreateShortcut($Path)
        $lnk.TargetPath = $Target
        $lnk.WorkingDirectory = $WorkDir
        $lnk.IconLocation = "$Icon,0"
        $lnk.Description = 'Abre Job Hunter'
        $lnk.Save()
    }

    # uv lee su configuracion de variables de entorno; se fijan solo durante
    # la instalacion y se restauran al final para no ensuciar la sesion.
    $uvEnv = @{
        UV_PYTHON_INSTALL_DIR = Join-Path $Tools 'python'
        UV_CACHE_DIR          = Join-Path $Tools 'cache'
        UV_PYTHON_PREFERENCE  = 'only-managed'
    }
    $savedEnv = @{}
    foreach ($key in $uvEnv.Keys) {
        $savedEnv[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
        [Environment]::SetEnvironmentVariable($key, $uvEnv[$key], 'Process')
    }

    try {
        Write-Host ''
        Write-Host '  Instalando Job Hunter' -ForegroundColor Green
        Write-Host "  Carpeta: $InstallDir"

        $isUpdate = Test-Path (Join-Path $InstallDir 'dashboard\app.py')
        if ($isUpdate -and (Test-PortOpen $Port)) {
            Write-Host ''
            Write-Host '  Job Hunter esta abierto. Cierra su ventana y vuelve a pegar el comando.' -ForegroundColor Yellow
            return
        }

        New-Item -ItemType Directory -Force -Path $InstallDir, $Tools, $TmpDir | Out-Null

        # 1. Codigo
        if ($env:JOBHUNTER_SOURCE) {
            Write-Step "Copiando el proyecto desde $env:JOBHUNTER_SOURCE"
            $src = $env:JOBHUNTER_SOURCE
        } else {
            Write-Step 'Descargando Job Hunter'
            $zip = Join-Path $TmpDir 'jobhunter.zip'
            Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/$Repo/archive/refs/heads/$Branch.zip" -OutFile $zip
            Expand-Archive -Path $zip -DestinationPath $TmpDir
            $src = (Get-ChildItem -Path $TmpDir -Directory | Select-Object -First 1).FullName
        }

        # Copia encima sin borrar nada: los datos del usuario no estan en el
        # repo, asi que una actualizacion nunca los pisa. Los excluidos cubren
        # el caso JOBHUNTER_SOURCE (una copia de trabajo con datos propios).
        robocopy $src $InstallDir /E /NFL /NDL /NJH /NJS /NP `
            /XD .git .venv venv data logs tools __pycache__ .pytest_cache '.test-tmp*' `
            /XF .env settings.yaml profile.yaml '*.bak' | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "No se pudo copiar el proyecto (robocopy $LASTEXITCODE)." }
        $global:LASTEXITCODE = 0

        # 2. uv (trae su propio Python; no hace falta tener Python instalado)
        if (-not (Test-Path $Uv)) {
            Write-Step 'Descargando uv (gestor de Python)'
            $uvZip = Join-Path $TmpDir 'uv.zip'
            Invoke-WebRequest -UseBasicParsing -Uri $UvUrl -OutFile $uvZip
            Expand-Archive -Path $uvZip -DestinationPath $Tools -Force
        }

        # 3. Python 3.12 + dependencias (python-jobspy fija numpy 1.26.3, que
        # no tiene binarios para Python 3.13+, de ahi la version fija)
        Push-Location $InstallDir
        try {
            if (-not (Test-Path '.venv\Scripts\python.exe')) {
                Write-Step 'Preparando Python 3.12'
                & $Uv venv .venv --python 3.12 --clear
                Assert-ExitCode 'Crear el entorno de Python'
            }
            Write-Step 'Instalando dependencias (la primera vez tarda un par de minutos)'
            & $Uv pip install --python .venv\Scripts\python.exe -r requirements.txt
            Assert-ExitCode 'Instalar dependencias'
        } finally {
            Pop-Location
        }

        # 4. Accesos directos
        $launcher = Join-Path $InstallDir 'JobHunter.bat'
        $icon = Join-Path $InstallDir 'assets\jobhunter.ico'
        if ($env:JOBHUNTER_NO_SHORTCUT -ne '1') {
            Write-Step 'Creando accesos directos'
            New-Shortcut (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Job Hunter.lnk') $launcher $InstallDir $icon
            New-Shortcut (Join-Path ([Environment]::GetFolderPath('Programs')) 'Job Hunter.lnk') $launcher $InstallDir $icon
        }

        Write-Host ''
        if ($isUpdate) {
            Write-Host '  Job Hunter se actualizo.' -ForegroundColor Green
        } else {
            Write-Host '  Job Hunter quedo instalado.' -ForegroundColor Green
        }
        Write-Host '  Abrelo con el icono "Job Hunter" del escritorio.'
        Write-Host '  Cerrar su ventana negra lo apaga.'
        Write-Host ''

        if ($env:JOBHUNTER_NO_LAUNCH -ne '1') {
            Start-Process -FilePath $launcher -WorkingDirectory $InstallDir
        }
    } catch {
        Write-Host ''
        Write-Host "  La instalacion no termino: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host '  Revisa tu conexion a internet y vuelve a pegar el comando.' -ForegroundColor Red
        Write-Host ''
    } finally {
        foreach ($key in $savedEnv.Keys) {
            [Environment]::SetEnvironmentVariable($key, $savedEnv[$key], 'Process')
        }
        Remove-Item -Recurse -Force -Path $TmpDir -ErrorAction SilentlyContinue
    }
}
