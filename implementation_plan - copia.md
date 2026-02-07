# Plan de Implementación del Proyecto
## Sistema de Novedades PGN con Integración HOMINIS

**Duración:** 2 meses 15 días (10.5 semanas)  
**Fecha Inicio:** 1 de Enero de 2026  
**Fecha Fin:** 15 de Marzo de 2026  
**Cliente:** Procuraduría General de la Nación

---

## Resumen Ejecutivo

Este plan establece la hoja de ruta para completar la implementación del sistema de extracción de novedades de decretos y certificaciones mediante OCR e IA, incluyendo el entrenamiento por refuerzo del modelo con validaciones de usuario, la integración con el sistema HOMINIS y la generación automática de certificados.

---

## Cronograma General

```mermaid
gantt
    title Plan de Implementación - Novedades PGN
    dateFormat  YYYY-MM-DD
    excludes    weekends
    
    section Fase 1: Procesamiento OCR
    Procesamiento Decretos Pendientes     :f1a, 2026-01-02, 10d
    Procesamiento Certificaciones         :f1b, 2026-01-02, 10d
    Alimentación BD Novedades            :f1c, after f1a, 5d
    
    section Fase 2: Entrenamiento Modelo
    Revisión Manual Huérfanos            :f2a, 2026-01-20, 15d
    Validación Hallazgos Usuario         :f2b, 2026-01-20, 15d
    Acumulación Ejemplos Aprendizaje     :f2c, 2026-01-20, 20d
    
    section Fase 3: Re-entrenamiento
    Fine-tuning Modelo LLM               :f3a, 2026-02-17, 5d
    Reprocesar Pendientes                :f3b, after f3a, 5d
    Procesar Nuevos Decretos             :f3c, after f3b, 3d
    Validación Experto TH/Jurídico       :f3d, after f3b, 5d
    
    section Fase 4: Integración HOMINIS
    Análisis API/BD HOMINIS              :f4a, 2026-02-24, 3d
    Desarrollo Conectores                :f4b, after f4a, 5d
    Migración Novedades                  :f4c, after f4b, 3d
    
    section Fase 5: Pruebas Validación
    Pruebas Cruzadas Decretos-HOMINIS    :f5a, 2026-03-05, 5d
    Validación Funcionarios Existentes   :f5b, 2026-03-05, 5d
    Corrección Discrepancias             :f5c, after f5a, 3d
    
    section Fase 6: Certificados Auto
    Desarrollo Generador Certificados    :f6a, 2026-03-10, 3d
    Integración LLM + HOMINIS            :f6b, after f6a, 2d
    Pruebas UAT                          :f6c, 2026-03-13, 2d
```

---

## Detalle de Fases

### FASE 1: Procesamiento OCR Completo
**Duración:** 3 semanas (2 - 17 Enero 2026)

| Actividad | Duración | Responsable | Entregable |
|-----------|----------|-------------|------------|
| Procesar decretos años faltantes | 10 días | Equipo Desarrollo | BD novedades actualizada |
| Procesar certificaciones actuales | 10 días | Equipo Desarrollo | Certificaciones digitalizadas |
| Alimentar BD novedades | 5 días | Equipo Desarrollo | Novedades vinculadas a decretos |

```mermaid
flowchart LR
    subgraph Entrada
        A[📁 Decretos PDF] 
        B[📁 Certificaciones]
    end
    
    subgraph Procesamiento
        C[🔍 Azure OCR]
        D[🤖 LLM Extracción]
    end
    
    subgraph Salida
        E[(BD Novedades)]
        F[(BD Certificaciones)]
    end
    
    A --> C --> D --> E
    B --> C --> D --> F
```

---

### FASE 2: Entrenamiento por Refuerzo
**Duración:** 4 semanas (20 Enero - 14 Febrero 2026)

| Actividad | Duración | Responsable | Entregable |
|-----------|----------|-------------|------------|
| Revisión decretos huérfanos | 15 días | Usuario + Experto TH | Correcciones validadas |
| Validación hallazgos discrepancias | 15 días | Usuario + Jurídico | Hallazgos resueltos |
| Acumulación ejemplos aprendizaje | 20 días | Sistema | Tabla ejemplos_aprendizaje poblada |

> [!IMPORTANT]
> **Recursos Requeridos:**
> - Experto en Talento Humano (Certificaciones)
> - Asesor Jurídico (Validación decretos)
> - Mínimo 500 ejemplos corregidos para fine-tuning efectivo

```mermaid
flowchart TB
    subgraph Usuario["👤 Validación Usuario"]
        A[Decretos Huérfanos]
        B[Hallazgos Pendientes]
    end
    
    subgraph Expertos["👥 Expertos"]
        C[Talento Humano]
        D[Jurídico]
    end
    
    subgraph Sistema["💾 Sistema"]
        E[(ejemplos_aprendizaje)]
        F[Correcciones Validadas]
    end
    
    A --> C --> F
    B --> D --> F
    F --> E
```

---

### FASE 3: Re-entrenamiento y Reprocesamiento
**Duración:** 2.5 semanas (17 Febrero - 5 Marzo 2026)

| Actividad | Duración | Responsable | Entregable |
|-----------|----------|-------------|------------|
| Fine-tuning modelo LLM | 5 días | Equipo IA | Modelo v2.0 optimizado |
| Reprocesar decretos pendientes | 5 días | Sistema | Pendientes clasificados |
| Procesar nuevos decretos | 3 días | Sistema | Decretos 2025-2026 procesados |
| Validación expertos | 5 días | Experto TH + Jurídico | Aprobación calidad |

```mermaid
flowchart LR
    A[(ejemplos_aprendizaje<br>500+ ejemplos)] --> B[🧠 Fine-tuning<br>GPT-4o-mini]
    B --> C[Modelo v2.0]
    C --> D[Reprocesar<br>Pendientes]
    C --> E[Procesar<br>Nuevos]
    D --> F{Validación<br>Expertos}
    E --> F
    F -->|OK| G[✅ Producción]
    F -->|Ajustar| B
```

---

### FASE 4: Integración con HOMINIS
**Duración:** 2 semanas (24 Febrero - 7 Marzo 2026)

| Actividad | Duración | Responsable | Entregable |
|-----------|----------|-------------|------------|
| Análisis API/BD HOMINIS | 3 días | Arquitecto + DBA | Documento integración |
| Desarrollo conectores | 5 días | Equipo Desarrollo | API REST conectores |
| Migración novedades | 3 días | DBA + Desarrollo | Novedades sincronizadas |

```mermaid
flowchart TB
    subgraph SistemaNovedades["Sistema Novedades PGN"]
        A[(novedades_pgn.db)]
        B[API Flask]
    end
    
    subgraph Integracion["Capa Integración"]
        C[Conector REST]
        D[Transformador Datos]
        E[Validador Integridad]
    end
    
    subgraph HOMINIS["Sistema HOMINIS"]
        F[(BD HOMINIS)]
        G[API HOMINIS]
    end
    
    A --> B --> C
    C --> D --> E
    E --> G --> F
```

---

### FASE 5: Pruebas de Validación Cruzada
**Duración:** 1.5 semanas (5 - 12 Marzo 2026)

| Actividad | Duración | Responsable | Entregable |
|-----------|----------|-------------|------------|
| Pruebas cruzadas Decretos-HOMINIS | 5 días | QA + Experto TH | Reporte discrepancias |
| Validación funcionarios existentes | 5 días | QA + Jurídico | Lista funcionarios validados |
| Corrección discrepancias | 3 días | Desarrollo + DBA | Datos consistentes |

> [!WARNING]
> **Criterios de Aceptación:**
> - 100% cédulas coinciden entre decretos y HOMINIS
> - 95% nombres con coincidencia exacta o fuzzy >90%
> - 0 novedades huérfanas sin funcionario asociado

---

### FASE 6: Generación Automática de Certificados
**Duración:** 1 semana (10 - 15 Marzo 2026)

| Actividad | Duración | Responsable | Entregable |
|-----------|----------|-------------|------------|
| Desarrollo generador certificados | 3 días | Equipo Desarrollo | Módulo generación PDF |
| Integración LLM + HOMINIS | 2 días | Equipo IA | Pipeline automatizado |
| Pruebas UAT | 2 días | Usuario Final | Certificados aprobados |

```mermaid
flowchart LR
    subgraph Entrada
        A[📝 Solicitud<br>Certificado]
    end
    
    subgraph Proceso
        B[(HOMINIS)]
        C[(Novedades)]
        D[🤖 LLM<br>Consolidación]
        E[📄 Generador PDF]
    end
    
    subgraph Salida
        F[📜 Certificado<br>Automático]
    end
    
    A --> B --> D
    A --> C --> D
    D --> E --> F
```

---

## Arquitectura de Integración Final

```mermaid
flowchart TB
    subgraph Fuentes["📁 Fuentes Documentales"]
        D1[Decretos PDF]
        D2[Certificaciones]
        D3[Actos Administrativos]
    end
    
    subgraph Procesamiento["⚙️ Motor IA"]
        OCR[Azure Document<br>Intelligence]
        LLM[GPT-4o-mini<br>Fine-tuned]
        VAL[Validador<br>Integridad]
    end
    
    subgraph Almacenamiento["💾 Bases de Datos"]
        NOV[(novedades_pgn.db)]
        APR[(ejemplos_aprendizaje)]
        HAL[(hallazgos_revision)]
    end
    
    subgraph Integracion["🔗 Integración"]
        API[API REST]
        CON[Conector HOMINIS]
    end
    
    subgraph HOMINIS["🏢 HOMINIS"]
        HOM[(BD HOMINIS)]
        FUNC[Funcionarios]
        HIST[Historial Laboral]
    end
    
    subgraph Salidas["📤 Salidas"]
        CERT[Certificados PDF]
        REP[Reportes]
        DASH[Dashboard]
    end
    
    D1 & D2 & D3 --> OCR --> LLM --> VAL
    VAL --> NOV
    VAL --> HAL
    LLM <--> APR
    
    NOV --> API --> CON --> HOM
    HOM --> FUNC & HIST
    
    FUNC & HIST --> CERT
    NOV --> REP & DASH
```

---

## Recursos del Proyecto

| Rol | Dedicación | Fase Participación |
|-----|------------|-------------------|
| Líder de Proyecto | 100% | Todas |
| Desarrollador Backend | 100% | F1, F3, F4, F6 |
| Especialista IA/ML | 50% | F2, F3, F6 |
| DBA | 30% | F4, F5 |
| Experto Talento Humano | 50% | F2, F3, F5 |
| Asesor Jurídico | 30% | F2, F3, F5 |
| QA/Tester | 50% | F5, F6 |
| Usuario Funcional | 30% | F2, F5, F6 |

---

## Hitos del Proyecto

| Hito | Fecha | Criterio de Éxito |
|------|-------|-------------------|
| 🏁 **Kick-off** | 2 Enero 2026 | Equipo conformado |
| 📊 **OCR Completo** | 17 Enero 2026 | 100% decretos procesados |
| 🎓 **Modelo Entrenado** | 21 Febrero 2026 | 500+ ejemplos, accuracy >90% |
| 🔗 **Integración HOMINIS** | 7 Marzo 2026 | Datos sincronizados |
| ✅ **Pruebas Aprobadas** | 12 Marzo 2026 | 0 errores críticos |
| 🚀 **Go-Live** | 15 Marzo 2026 | Sistema en producción |

---

## Riesgos y Mitigación

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Calidad OCR insuficiente | Media | Alto | Reprocesar con parámetros ajustados |
| Pocos ejemplos para fine-tuning | Media | Alto | Extender fase 2, priorizar revisión |
| API HOMINIS no disponible | Baja | Crítico | Plan B: integración por BD |
| Expertos no disponibles | Media | Alto | Programar sesiones anticipadas |

---

## Verificación del Plan

### Validación por Fase:
1. **F1:** Contar registros en BD novedades vs archivos origen
2. **F2:** Métricas de ejemplos_aprendizaje (count, distribución por código)
3. **F3:** Comparar accuracy antes/después fine-tuning
4. **F4:** Test conectividad API HOMINIS
5. **F5:** Reporte cruzado cédulas Decretos ↔ HOMINIS
6. **F6:** Generar 10 certificados de prueba, validación usuario

### Comando de Verificación Rápida:
```bash
# Verificar estado actual de la BD
sqlite3 novedades_pgn.db "
SELECT 'Decretos' as tipo, COUNT(*) as total FROM decretos
UNION ALL SELECT 'Novedades', COUNT(*) FROM novedades
UNION ALL SELECT 'Funcionarios', COUNT(*) FROM funcionarios
UNION ALL SELECT 'Ejemplos Aprendizaje', COUNT(*) FROM ejemplos_aprendizaje
UNION ALL SELECT 'Hallazgos Pendientes', COUNT(*) FROM hallazgos_revision WHERE estado='PENDIENTE';
"
```

---

> [!NOTE]
> Este plan está sujeto a ajustes según disponibilidad de recursos y prioridades institucionales. Se recomienda revisión semanal de avance con el comité de proyecto.
