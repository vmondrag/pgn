# ============================================================================
# Script de Monitoreo de Extracciones de Decretos
# ============================================================================
# Este script monitorea los procesos de extraccion activos y lanza nuevos
# procesos de la cola cuando uno de los actuales termina.
# 
# USO: .\monitor_extractions.ps1
# ============================================================================

$ErrorActionPreference = "Continue"

# Configuracion: Maximo de procesos concurrentes
$MAX_CONCURRENT = 3

# Cola de procesos pendientes
$pendingJobs = @(
       @{
        Year = "2019"
        DirIn = "C:\temp\PNG_CERTIFICADO_V3\Decretos\2019"
        OutputDir = "output_2019_hybrid"
    },
    @{
        Year = "2020"
        DirIn = "C:\temp\PNG_CERTIFICADO_V3\Decretos\2020"
        OutputDir = "output_2020_hybrid"
    },
    @{
        Year = "2021"
        DirIn = "C:\temp\PNG_CERTIFICADO_V3\Decretos\2021"
        OutputDir = "output_2021_hybrid"
    },
    @{
        Year = "2022"
        DirIn = "C:\temp\PNG_CERTIFICADO_V3\Decretos\2022"
        OutputDir = "output_2022_hybrid"
    },
    @{
        Year = "2023"
        DirIn = "C:\temp\PNG_CERTIFICADO_V3\Decretos\2023"
        OutputDir = "output_2023_hybrid"
    },
    @{
        Year = "2024"
        DirIn = "C:\temp\PNG_CERTIFICADO_V3\Decretos\2024"
        OutputDir = "output_2024_hybrid"
    },
    @{
        Year = "2025"
        DirIn = "C:\temp\PNG_CERTIFICADO_V3\Decretos\2025"
        OutputDir = "output_2025_hybrid"
    }
)

$pendingQueue = [System.Collections.ArrayList]::new($pendingJobs)
$completedYears = @()
$startedYears = @()

function Get-RunningExtractions {
    $processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue
    $extractions = @()
    
    foreach ($proc in $processes) {
        if ($proc.CommandLine -match "extract_hybrid\.py.*Decretos\\(\d{4})") {
            $year = $matches[1]
            $extractions += @{
                ProcessId = $proc.ProcessId
                Year = $year
                CommandLine = $proc.CommandLine
            }
        }
    }
    return $extractions
}

function Start-Extraction {
    param([hashtable]$job)
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] INICIANDO extraccion para ano $($job.Year)" -ForegroundColor Green
    
    $arguments = "extract_hybrid.py --dir-in `"$($job.DirIn)`" --llm gpt-oss:20b --output-dir $($job.OutputDir)"
    Write-Host "  Comando: python $arguments" -ForegroundColor DarkGray
    
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "python"
    $psi.Arguments = $arguments
    $psi.WorkingDirectory = "C:\temp\PNG_CERTIFICADO_V3"
    $psi.UseShellExecute = $true
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Minimized
    
    $process = [System.Diagnostics.Process]::Start($psi)
    $script:startedYears += $job.Year
    
    Write-Host "  PID: $($process.Id)" -ForegroundColor DarkGray
    return $process.Id
}

function Write-Status {
    param(
        [array]$running,
        [int]$pending,
        [array]$completed
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor DarkCyan
    Write-Host "[$timestamp] ESTADO DEL MONITOREO" -ForegroundColor White
    Write-Host "===========================================================" -ForegroundColor DarkCyan
    
    $runningYearsList = if ($running.Count -gt 0) { $running.Year -join ", " } else { "ninguno" }
    Write-Host "  Ejecutando: $runningYearsList" -ForegroundColor Yellow
    Write-Host "  Pendientes: $pending" -ForegroundColor Yellow
    
    $completedList = if ($completed.Count -gt 0) { $completed -join ", " } else { "ninguno" }
    Write-Host "  Completados: $completedList" -ForegroundColor Green
    Write-Host "===========================================================" -ForegroundColor DarkCyan
}

# ============================================================================
# INICIO DEL MONITOREO
# ============================================================================

Clear-Host
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "   MONITOR DE EXTRACCIONES DE DECRETOS - PNG CERTIFICADO" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Maximo procesos concurrentes: $MAX_CONCURRENT" -ForegroundColor White
$yearsInQueue = $pendingJobs.Year -join ", "
Write-Host "  Anos en cola: $yearsInQueue" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Presione Ctrl+C para detener el monitoreo" -ForegroundColor DarkGray
Write-Host ""

$previousRunning = @()
$checkInterval = 60

while ($true) {
    $currentRunning = Get-RunningExtractions
    $runningYears = @()
    if ($currentRunning.Count -gt 0) {
        $runningYears = $currentRunning.Year | Sort-Object -Unique
    }
    
    # Detectar procesos que terminaron
    foreach ($prev in $previousRunning) {
        if ($prev.Year -notin $runningYears -and $prev.Year -notin $completedYears) {
            $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            Write-Host "[$timestamp] COMPLETADO - Ano $($prev.Year) ha terminado" -ForegroundColor Green
            $completedYears += $prev.Year
        }
    }
    
    # Iniciar nuevos procesos si hay espacio
    while ($currentRunning.Count -lt $MAX_CONCURRENT -and $pendingQueue.Count -gt 0) {
        $nextJob = $pendingQueue[0]
        $pendingQueue.RemoveAt(0)
        
        $newPid = Start-Extraction -job $nextJob
        Start-Sleep -Seconds 5
        
        $currentRunning = Get-RunningExtractions
    }
    
    # Mostrar estado
    Write-Status -running $currentRunning -pending $pendingQueue.Count -completed $completedYears
    
    # Verificar si todo ha terminado
    if ($currentRunning.Count -eq 0 -and $pendingQueue.Count -eq 0) {
        Write-Host ""
        Write-Host "================================================================" -ForegroundColor Green
        Write-Host "      TODAS LAS EXTRACCIONES HAN TERMINADO!" -ForegroundColor Green
        Write-Host "================================================================" -ForegroundColor Green
        Write-Host ""
        $completedList = $completedYears -join ", "
        Write-Host "  Anos completados: $completedList" -ForegroundColor Cyan
        break
    }
    
    $previousRunning = $currentRunning
    
    Write-Host "  Proxima verificacion en $checkInterval segundos..." -ForegroundColor DarkGray
    Start-Sleep -Seconds $checkInterval
}

Write-Host ""
Write-Host "Monitoreo finalizado." -ForegroundColor White
