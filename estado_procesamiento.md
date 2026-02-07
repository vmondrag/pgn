# Estado del Procesamiento de Archivos Faltantes

**Fecha de inicio:** 2026-01-17 23:31:27
**Última actualización:** 2026-01-17 23:33:00

---

## Comandos Ejecutados

### ✅ Año 2016 - COMPLETADO
```bash
python extract_decretos.py --dir-in C:\temp\PNG_CERTIFICADO_V3\Decretos\2016 --llm gpt-oss:20b-cloud
```

**Resultado:**
- Archivos encontrados: 6,042
- Archivos ya procesados (saltados): 6,037
- Archivos procesados esta sesión: 5
  - ✅ Exitosos: 3 (60%)
  - ❌ Con errores: 2 (40%)

**Archivos con errores:**
- NO FISICO DECRETO 4694-4698-2016.pdf
- NO FISICO DECRETO 4704-2016.pdf

---

### 🔄 Año 2020 - EN PROCESO
```bash
python extract_decretos.py --dir-in C:\temp\PNG_CERTIFICADO_V3\Decretos\2020 --llm gpt-oss:20b-cloud
```

**Estado:** ACTIVO
**ID de comando:** 27e79e8e-6a6f-4dc5-bf4e-f2a8920f7a7b
**Archivos a procesar:** 119

---

### 🔄 Año 2018 - EN PROCESO
```bash
python extract_decretos.py --dir-in C:\temp\PNG_CERTIFICADO_V3\Decretos\2018 --llm gpt-oss:20b-cloud
```

**Estado:** ACTIVO
**ID de comando:** 8148f650-1e3c-4803-bb78-7d6c7d8b4693
**Progreso:** 2 / 843 archivos (0.2%)
**Tiempo estimado:** ~14 horas

**Archivos procesados:**
1. ✅ DECRETO 3576-2018.pdf
2. ✅ DECRETO 3577-2018 (1).pdf

---

### ✅ Resoluciones 2024 - YA PROCESADAS
```bash
python extract_resoluciones.py --dir-in "C:\temp\PNG_CERTIFICADO_V3\Decretos\RESOLUCIONES 2024" --llm gpt-oss:120b-cloud
```

**Resultado:**
- Archivos encontrados: 342
- Archivos ya procesados (saltados): 342
- Archivos pendientes: 0

**Conclusión:** Los 2 archivos que aparecían como no procesados en la verificación inicial ya fueron procesados en una ejecución anterior.

---

## Resumen de Progreso

| Año | Estado | Procesados | Pendientes | % Completado |
|-----|--------|-----------|------------|--------------|
| 2016 | ✅ Completado | 3/5 | 2 (errores) | 60% |
| 2018 | 🔄 En proceso | 2/843 | 841 | 0.2% |
| 2020 | 🔄 En proceso | ?/119 | ? | En curso |
| Res 2024 | ✅ Ya completo | 342/342 | 0 | 100% |

---

## Comandos para Monitorear Progreso

### Verificar estado del año 2020:
```python
# En Python o script
from subprocess import run
result = run(['python', '-c', 'import subprocess; print(subprocess.check_output(["tasklist"]))'], capture_output=True)
```

### Verificar estado del año 2018:
El proceso está activo y procesando aproximadamente 1 archivo por minuto.

### Verificar archivos procesados:
```bash
python verificar_procesamiento.py
```

---

## Notas

1. **SyntaxWarning en extract_decretos.py línea 6:** Warning benigno sobre secuencia de escape en una cadena de documentación. No afecta la funcionalidad.

2. **Archivos "NO FISICO" con errores:** Los 2 archivos del 2016 que fallaron tienen el prefijo "NO FISICO", sugiriendo que pueden tener un formato especial o estar corruptos.

3. **Procesamiento automático de omisión:** Los scripts están saltando correctamente los archivos ya procesados, procesando solo los faltantes.

---

**Próximos pasos:** Los procesos continuarán ejecutándose en segundo plano. El año 2018 tomará aproximadamente 14 horas en completarse dado el volumen de archivos (843).
