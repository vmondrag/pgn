# Documentación del Script de Verificación Completa

## 2026_01_18_verificaciones_full.py

### Descripción

Script completo de verificación del sistema que valida la integridad de todos los archivos PDF procesados contra sus outputs y registros en la base de datos.

### Funcionalidades

1. **Verificación de Decretos (2009-2025)**
   - Valida todos los PDFs en `C:\temp\PNG_CERTIFICADO_V3\Decretos\YYYY`
   - Verifica existencia de output en `output_YYYY_hybrid\graphrag\`
   - Consulta registros en tabla `decretos` de la base de datos

2. **Verificación de Resoluciones (2023-2025)**
   - Valida todos los PDFs en directorios `RESOLUCIONES`
   - Verifica existencia de output en `output_res_YYYY\graphrag\`
   - Consulta registros en tabla `resoluciones` de la base de datos

3. **Detección de Inconsistencias**
   - Archivos con output pero sin registro en BD
   - Archivos con registro en BD pero sin output
   - Archivos sin output ni registro en BD

4. **Generación de Reportes**
   - Estadísticas generales (totales, porcentajes)
   - Lista detallada de todas las inconsistencias
   - Formato Markdown para fácil lectura

### Uso

#### Modo Test (10 archivos por año)
```bash
python 2026_01_18_verificaciones_full.py --test
```
o
```bash
python 2026_01_18_verificaciones_full.py -t
```

#### Modo Producción (todos los archivos)
```bash
python 2026_01_18_verificaciones_full.py
```

### Salida

Genera archivo: `log_verificacion_pdf_salida_bd.md`

### Resultados del Test

**Prueba realizada:** 2026-01-18 07:45:27  
**Archivos verificados:** 200 (10 por cada año)

#### Estadísticas:
- Total PDFs verificados: 200
- Con output: 198 (99.00%)
- Sin output: 2 (1.00%)
- Con registro en BD: 200 (100.00%)
- Sin registro en BD: 0 (0.00%)
- **Completos (output + BD): 198 (99.00%)**

#### Inconsistencias Detectadas: 2

1. **RESOLUCION 030 DE 2024.pdf**
   - ID BD: 1
   - Problema: Está en BD pero NO tiene output

2. **RESOLUCION 321 DE 30 DE SEPTIEMBRE DE 2024.pdf**
   - ID BD: 3
   - Problema: Está en BD pero NO tiene output

### Estructura del Script

```python
class VerificadorSistema:
    - __init__(test_mode, test_limit)
    - conectar_bd()
    - verificar_decreto(pdf_path, anio)
    - verificar_resolucion(pdf_path, anio)
    - verificar_decretos_anio(anio)
    - verificar_resoluciones_anio(anio)
    - generar_reporte_md()
    - ejecutar()
```

### Líneas de Código

- Total: ~440 líneas
- Clases: 1
- Métodos: 8
- Funcionalidad completa con manejo de errores y estadísticas

### Dependencias

- `sqlite3` (built-in)
- `pathlib` (built-in)
- `datetime` (built-in)

### Características Técnicas

- ✅ Modo test y producción
- ✅ Validación completa PDF → Output → BD
- ✅ Estadísticas detalladas
- ✅ Reporte en Markdown
- ✅ Manejo de errores
- ✅ Compatible con estructura actual del sistema
- ✅ Sin dependencias externas

### Próximos Pasos

Para ejecutar verificación completa del sistema (producción):
```bash
python 2026_01_18_verificaciones_full.py
```

**Nota:** La verificación completa procesará ~54,000 archivos y tomará aproximadamente 15-30 minutos dependiendo del sistema.

### Conclusión del Test

✅ **Test exitoso**  
✅ Script funcionando correctamente  
✅ Detección de inconsistencias operativa  
✅ Formato de reporte adecuado  
✅ Listo para ejecución en producción
