# Monitor de ejecucion de extract_resoluciones.py
# Espera 1 hora y luego ejecuta las extracciones de 2024 y 2025

Write-Host "=============================================="
Write-Host "MONITOR DE EXTRACCION DE RESOLUCIONES PGN"
Write-Host "=============================================="
Write-Host ""
Write-Host "Hora de inicio: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host ""
Write-Host "Este script esperara 1 hora y luego ejecutara:"
Write-Host "  1. Extraccion RESOLUCIONES 2024"
Write-Host "  2. Extraccion RESOLUCIONES 2025"
Write-Host ""
Write-Host "----------------------------------------------"
Write-Host "Esperando 1 hora antes de iniciar..."
Write-Host "Hora estimada de inicio: $((Get-Date).AddHours(1).ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host "----------------------------------------------"
Write-Host ""

# Esperar 1 hora (3600 segundos)
Start-Sleep -Seconds 3600

Write-Host ""
Write-Host "=============================================="
Write-Host "INICIANDO EXTRACCION RESOLUCIONES 2024"
Write-Host "Hora: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "=============================================="
Write-Host ""

# Ejecutar extraccion 2024
$proceso2024 = Start-Process -FilePath "python" -ArgumentList @(
    "extract_resoluciones.py",
    "--dir-in", "C:\temp\PNG_CERTIFICADO_V3\Decretos\RESOLUCIONES 2024",
    "--llm", "gpt-oss:120b-cloud",
    "--output", "C:\temp\output_res_2024"
) -WorkingDirectory "C:\temp\PNG_CERTIFICADO_V3" -Wait -NoNewWindow -PassThru

Write-Host ""
Write-Host "Extraccion 2024 finalizada con codigo: $($proceso2024.ExitCode)"
Write-Host "Hora: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host ""

Write-Host "=============================================="
Write-Host "INICIANDO EXTRACCION RESOLUCIONES 2025"
Write-Host "Hora: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "=============================================="
Write-Host ""

# Ejecutar extraccion 2025
$proceso2025 = Start-Process -FilePath "python" -ArgumentList @(
    "extract_resoluciones.py",
    "--dir-in", "C:\temp\PNG_CERTIFICADO_V3\Decretos\RESOLUCIONES 2025",
    "--llm", "gpt-oss:120b-cloud",
    "--output", "C:\temp\output_res_2025"
) -WorkingDirectory "C:\temp\PNG_CERTIFICADO_V3" -Wait -NoNewWindow -PassThru

Write-Host ""
Write-Host "Extraccion 2025 finalizada con codigo: $($proceso2025.ExitCode)"
Write-Host ""

Write-Host "=============================================="
Write-Host "PROCESO COMPLETO"
Write-Host "Hora de finalizacion: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "=============================================="

# Mantener ventana abierta
Write-Host ""
Write-Host "Presione cualquier tecla para cerrar..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
