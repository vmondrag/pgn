# Lista de los 22 Errores de Procesamiento

**Fuente:** Base de datos `novedades_pgn.db`  
**Endpoint:** http://localhost:5000/errores  
**Fecha de consulta:** 2026-01-18 06:36

---

## Resumen Ejecutivo

**Total de errores registrados:** 22  
**Tipo de errores:** EXTRACCION (100%)

### Desglose por Mensaje de Error:

| Tipo de Error | Cantidad | Descripción |
|---------------|----------|-------------|
| **ERROR_NO_FITZ** | 20 | Error al cargar librería PyMuPDF (fitz) para extracción de PDF |
| **ERROR_OCR** | 2 | Error en el proceso de OCR (archivos "NO FISICO") |

---

## Lista Completa de Errores

### Grupo 1: Archivos del Año 2016 (2 errores)

#### 1. NO FISICO DECRETO 4694-4698-2016.pdf
- **ID:** 22
- **Ruta:** `C:\temp\PNG_CERTIFICADO_V3\Decretos\2016\NO FISICO DECRETO 4694-4698-2016.pdf`
- **Error:** ERROR_OCR
- **Tipo:** EXTRACCION
- **Fecha:** 2026-01-18 04:33:42
- **Nota:** Archivo con formato especial "NO FISICO" (consolidación de múltiples decretos)

#### 2. NO FISICO DECRETO 2675-2676-2016.pdf
- **ID:** 21
- **Ruta:** `C:\temp\PNG_CERTIFICADO_V3\Decretos\2016\NO FISICO DECRETO 2675-2676-2016.pdf`
- **Error:** ERROR_OCR
- **Tipo:** EXTRACCION
- **Fecha:** 2026-01-18 04:33:22
- **Nota:** Archivo con formato especial "NO FISICO" (consolidación de múltiples decretos)

---

### Grupo 2: Archivos del Año 2009 (20 errores - DUPLICADOS)

> **⚠️ IMPORTANTE:** Los siguientes 10 archivos aparecen **duplicados** en la base de datos de errores (IDs 1-10 y 11-20), lo que indica que fueron procesados dos veces con el mismo resultado de error.

#### Archivos Únicos con Error (10 archivos):

##### 3-4. DECRETO 001-2009.pdf (DUPLICADO)
- **IDs:** 11, 1
- **Ruta:** `C:\temp\PNG_CERTIFICADO_V3\Decretos\2009\DECRETO 001-2009.pdf`
- **Error:** ERROR_NO_FITZ
- **Fechas:** 2025-12-19 18:08:00, 2025-12-19 18:07:25

##### 5-6. DECRETO 002-2009.pdf (DUPLICADO)
- **IDs:** 12, 2
- **Ruta:** `C:\temp\PNG_CERTIFICADO_V3\Decretos\2009\DECRETO 002-2009.pdf`
- **Error:** ERROR_NO_FITZ
- **Fechas:** 2025-12-19 18:08:00, 2025-12-19 18:07:25

##### 7-8. DECRETO 003 2009.pdf (DUPLICADO)
- **IDs:** 13, 3
- **Ruta:** `C:\temp\PNG_CERTIFICADO_V3\Decretos\2009\DECRETO 003 2009.pdf`
- **Error:** ERROR_NO_FITZ
- **Fechas:** 2025-12-19 18:08:00, 2025-12-19 18:07:25
- **Nota:** Archivo con espacio en lugar de guión en el nombre

##### 9-10. DECRETO 004-2009.pdf (DUPLICADO)
- **IDs:** 14, 4
- **Ruta:** `C:\temp\PNG_CERTIFICADO_V3\Decretos\2009\DECRETO 004-2009.pdf`
- **Error:** ERROR_NO_FITZ
- **Fechas:** 2025-12-19 18:08:00, 2025-12-19 18:07:25

##### 11-12. DECRETO 005-2009.pdf (DUPLICADO)
- **IDs:** 15, 5
- **Ruta:** `C:\temp\PNG_CERTIFICADO_V3\Decretos\2009\DECRETO 005-2009.pdf`
- **Error:** ERROR_NO_FITZ
- **Fechas:** 2025-12-19 18:08:00, 2025-12-19 18:07:25

##### 13-14. DECRETO 006-2009.pdf (DUPLICADO)
- **IDs:** 16, 6
- **Ruta:** `C:\temp\PNG_CERTIFICADO_V3\Decretos\2009\DECRETO 006-2009.pdf`
- **Error:** ERROR_NO_FITZ
- **Fechas:** 2025-12-19 18:08:00, 2025-12-19 18:07:25

##### 15-16. DECRETO 007-2009.pdf (DUPLICADO)
- **IDs:** 17, 7
- **Ruta:** `C:\temp\PNG_CERTIFICADO_V3\Decretos\2009\DECRETO 007-2009.pdf`
- **Error:** ERROR_NO_FITZ
- **Fechas:** 2025-12-19 18:08:00, 2025-12-19 18:07:25

##### 17-18. DECRETO 008-2009.pdf (DUPLICADO)
- **IDs:** 18, 8
- **Ruta:** `C:\temp\PNG_CERTIFICADO_V3\Decretos\2009\DECRETO 008-2009.pdf`
- **Error:** ERROR_NO_FITZ
- **Fechas:** 2025-12-19 18:08:00, 2025-12-19 18:07:25

##### 19-20. DECRETO 009-2009.pdf (DUPLICADO)
- **IDs:** 19, 9
- **Ruta:** `C:\temp\PNG_CERTIFICADO_V3\Decretos\2009\DECRETO 009-2009.pdf`
- **Error:** ERROR_NO_FITZ
- **Fechas:** 2025-12-19 18:08:00, 2025-12-19 18:07:25

##### 21-22. DECRETO 010-2009.pdf (DUPLICADO)
- **IDs:** 20, 10
- **Ruta:** `C:\temp\PNG_CERTIFICADO_V3\Decretos\2009\DECRETO 010-2009.pdf`
- **Error:** ERROR_NO_FITZ
- **Fechas:** 2025-12-19 18:08:00, 2025-12-19 18:07:25

---

## Análisis de Errores

### ERROR_NO_FITZ (20 registros, 10 archivos únicos)

**Causa:** Librería PyMuPDF (fitz) no pudo abrir o leer los archivos PDF.

**Archivos afectados:**
- DECRETO 001-2009.pdf a DECRETO 010-2009.pdf (primeros 10 decretos del 2009)

**Posibles causas:**
1. **PDFs corruptos o dañados**
2. **Formato PDF no estándar o antiguo** (año 2009)
3. **PDFs protegidos con contraseña**
4. **Archivos que no son PDFs reales** (extensión .pdf pero contenido diferente)

**Solución recomendada:**
1. Verificar manualmente la integridad de los archivos
2. Intentar abrir con diferentes lectores de PDF
3. Re-escanear los documentos originales si están disponibles
4. Usar herramientas de reparación de PDF

---

### ERROR_OCR (2 archivos)

**Causa:** Fallo en el servicio de OCR (NIM PaddleOCR) al intentar procesar las imágenes.

**Archivos afectados:**
- NO FISICO DECRETO 4694-4698-2016.pdf
- NO FISICO DECRETO 2675-2676-2016.pdf

**Características especiales:**
- Ambos tienen el prefijo "NO FISICO"
- Probablemente
 contienen múltiples decretos consolidados
- Pueden tener formato de escaneo de baja calidad
- Estructura no estándar

**Posibles causas:**
1. **Calidad de imagen muy baja** (escaneados mal)
2. **Múltiples decretos en un solo PDF** (confunde al OCR)
3. **Formato especial** que requiere procesamiento manual
4. **Timeout del servicio OCR** por tamaño o complejidad

**Solución recomendada:**
1. Revisar manualmente estos archivos
2. Mejorar la calidad de las imágenes si es posible
3. Dividir los PDFs consolidados en archivos individuales
4. Ajustar parámetros de timeout del servicio OCR

---

## Resumen de Archivos Únicos con Error

| Año | Archivos Únicos | Tipo de Error | Estado |
|-----|-----------------|---------------|--------|
| **2009** | 10 | ERROR_NO_FITZ | ⚠️ Requieren revisión manual |
| **2016** | 2 | ERROR_OCR | ⚠️ Archivos especiales "NO FISICO" |
| **TOTAL** | **12** | - | - |

**Nota:** Los 22 errores registrados corresponden a **12 archivos únicos**, ya que los 10 archivos del 2009 aparecen duplicados en la tabla de errores.

---

## Recomendaciones

### Inmediatas:
1. **Limpiar duplicados** en la tabla de errores (IDs 1-10)
2. **Revisar manualmente** los 10 archivos del 2009
3. **Investigar causa** del ERROR_NO_FITZ en archivos 2009

### Mediano Plazo:
1. **Re-procesar archivos 2009** después de validar/reparar los PDFs
2. **Procesamiento manual** de los 2 archivos "NO FISICO" del 2016
3. **Establecer proceso** para archivos con formatos especiales

### Impacto en el Sistema:
- **Archivos únicos con error:** 12 de 54,209 total (**0.02%**)
- **Cobertura de procesamiento:** **99.98%**
- **Estado general:** ✅ Excelente

---

**Conclusión:** El sistema tiene un desempeño excepcional con solo 12 archivos únicos con errores de un total de más de 54,000 archivos procesados.
