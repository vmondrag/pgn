# ANÁLISIS DE PATRONES EN DECRETOS HUÉRFANOS DE LA PGN
# =====================================================
# Basado en muestra de 25 decretos huérfanos (2009-2014)

ANALISIS_PATRONES = """
## TIPOS DE DECRETO IDENTIFICADOS (con ejemplos reales)

### 1. NOMBRAMIENTO PROVISIONAL (código: N)
Patrón: "Nombrar en Provisionalidad, a [NOMBRE], cedula [X], en el cargo de [CARGO], en el cargo de [PERSONA_REEMPLAZADA]"
Ejemplo: "Nombrar en Provisionalidad, a CLAUDIA PATRICIA QUINTERO RAMIREZ, quien se identifica con la Cedula de Ciudadania No.43.168.876, en el cargo de Auxiliar de Servicios Generales, Codigo 6AS Grado 03, de la Procuraduria Provincial del Valle de Aburra, en el cargo de LUZ DARY QUINTERO CASTANO."
→ Funcionario: CLAUDIA PATRICIA QUINTERO RAMIREZ (43168876)
→ Persona reemplazada: LUZ DARY QUINTERO CASTANO (sin novedad)

### 2. ENCARGO (código: E)
Patrón: "Encargar, a [NOMBRE], [CARGO_ACTUAL] Codigo XX, del cargo de [CARGO_ENCARGADO], en el cargo de [PERSONA_REEMPLAZADA]"
Ejemplo: "Encargar, a JANNETH PEREZ RAMIREZ, quien se identifica con la Cedula de Ciudadania No. 52.123.429, Oficinista Codigo 5OF Grado 06, de la Procuraduria Delegada para la Vigilancia Preventiva de la Funcion Publica, del cargo de Profesional Universitario Codigo 3PU Grado 15, de la Procuraduria Delegada para los Asuntos del Trabajo y la Seguridad Social, en el cargo de MARTIN ALEJANDRO CAMACHO ALDANA"
→ cargo_actual: Oficinista Código 5OF Grado 06
→ cargo (encargado): Profesional Universitario Código 3PU Grado 15
→ Persona reemplazada: MARTIN ALEJANDRO CAMACHO ALDANA

### 3. RENUNCIA (código: R)
Patrón: "Aceptar, la renuncia presentada por [NOMBRE], quien se identifica con la Cedula [X]"
Ejemplo: "Aceptar, la renuncia presentada por el Auxiliar Juridico Ad-honorem DANIEL LAUREANO NOGUERA SANTANDER, quien se identifica con la Cedula de Ciudadania No.1.085.248.516."

### 4. ASIGNACIÓN DE FUNCIONES (código: ASIG)
Patrón: "Asignar funciones, a [NOMBRE], [CARGO], funciones en [DEPENDENCIA_DESTINO]"
Ejemplo: "Asignar, a GERMAN VILLABON MAHECHA quien se identifica con la Cedula de Ciudadania No.14.319.171, oficinista, Codigo 50F, Grado 06 de la Procuraduria Provincial de Ibague, funciones en la Division Administrativa-Grupo de Inmuebles."
→ No hay persona reemplazada, es movimiento de funciones sin cambio de cargo

### 5. PRÓRROGA (código: PROR)
Patrón: "Prorrogar, [tipo], a [NOMBRE], [CARGO/ENCARGO]"
Ejemplos:
- "Prorrogar el encargo a ELAYNE LILIANA LEON OMANA..."
- "Prorrogar, la provisionalidad, hasta por seis (6) meses, a DIANA MARCELA CABANZO SANCHEZ..."

### 6. REVOCACIÓN DE DECRETO (código: MD - Modificación)
Patrón: "Revocar el Decreto No.[X] del [fecha]"
Ejemplo: "Revocar el Decreto No.1417 del 18 de abril de 2013"
→ NO hay funcionario ni cédula, es modificación administrativa

### 7. ACLARACIÓN DE DECRETO (código: MD)
Patrón: "Aclarar el Decreto No.[X]...en el sentido de que [corrección]"
Ejemplo: "Aclarar el Decreto No.1431 del 3 de julio de 2009 en el sentido de que el nombre de la Doctora LUZ ESTELLA GARCIA DE BONILLA...corresponde en la actualidad a LUZ ESTELLA GARCIA FORERO"
→ Es corrección de datos, no una novedad de personal

### 8. NOMBRAMIENTO AD HONOREM MÚLTIPLE (código: NAADH)
Patrón: "Por el cual se hacen unos nombramientos de auxiliar juridico ad-honorem"
Ejemplo: Decreto 2852-2011 con múltiples funcionarios
→ Puede tener MUCHOS funcionarios en un solo decreto

### 9. COMISIÓN (código: C)
Patrón: "Prorrogar...Comision, a [NOMBRE]...para ejercer el cargo de [CARGO]"
Ejemplo: "Prorrogar, hasta por dos (2) meses, Comision, a FADUL RINCONES MARTINEZ...Profesional Universitario, Codigo 3PU, Grado 17...para ejercer el cargo de Procurador 196 Judicial I Penal de Apartado"

## ERRORES OCR FRECUENTES DETECTADOS

1. Palabras pegadas en encabezado:
   - "GENERALDELANACION" → "GENERAL DE LA NACION"
   - "PROCURADURIA" → correcto (sin espacios)
   
2. Fechas pegadas:
   - "25MAR2014" → "25 MAR 2014"
   - "27AG02009" → "27 AGO 2009"
   - "3 0 AG02011" → "30 AGO 2011" (espacios erróneos)
   
3. Números de decreto con espacios:
   - "No.1 853" → "No.1853"
   - "No.3 852" → "No.3852"
   
4. Cédulas con puntos:
   - "No.43.168.876" → "43168876"
   - "No.79.146..050" → "79146050" (doble punto)
   
5. Códigos de cargo pegados al texto:
   - "Codigo50FGrado06" → "Codigo 5OF Grado 06"
   - "OficinistaCodigo50F" → "Oficinista Codigo 5OF"

## DECRETOS ESPECIALES (SIN FUNCIONARIOS)

Algunos decretos NO tienen funcionarios asociados:
- Revocaciones de decretos anteriores
- Aclaraciones de decretos
- Modificaciones administrativas

Para estos, usar código "MD" (Modificación Decreto) y funcionario_id = NULL
"""

# Prompt optimizado basado en análisis
PROMPT_OPTIMIZADO_V3 = '''Eres un experto legal especializado en análisis de decretos administrativos de la Procuraduría General de la Nación (PGN) de Colombia.

=== CONTEXTO LEGAL ===
Los decretos de la PGN regulan novedades de personal: nombramientos, encargos, renuncias, comisiones, traslados, etc.
Marco normativo: Ley 909 de 2004, Decreto 262 de 2000, Art. 125 Constitución Política.

=== INFORMACIÓN DEL DECRETO ===
- Número: {numero_decreto}
- Año: {anio}

=== TEXTO OCR (puede tener errores) ===
{texto_ocr}

=== ERRORES OCR COMUNES - SEPARA MENTALMENTE ===
- "GENERALDELANACION" = "GENERAL DE LA NACION"
- "25MAR2014" = "25 MAR 2014"
- "27AG02009" = "27 AGO 2009"
- "No.43.168.876" = cédula 43168876
- "Codigo50FGrado06" = "Codigo 5OF Grado 06"
- "OficinistaCodigo" = "Oficinista Codigo"

=== TIPOS DE DECRETO ===

1. NOMBRAMIENTO (N):
   Patrón: "Nombrar en Provisionalidad, a [NOMBRE], cedula [X], en el cargo de [CARGO]"
   → cargo = cargo al que se nombra
   → Artículo siguiente menciona "en el cargo de [PERSONA]" = persona reemplazada (sin novedad)

2. ENCARGO (E):
   Patrón: "Encargar, a [NOMBRE], [CARGO_ACTUAL], del cargo de [CARGO_ENCARGADO]"
   → cargo_actual = cargo que YA tiene
   → cargo = cargo que asume temporalmente (CARGO_ENCARGADO)
   → "en el cargo de [PERSONA]" = persona reemplazada (sin novedad)

3. RENUNCIA (R):
   Patrón: "Aceptar, la renuncia presentada por [NOMBRE]"
   
4. ASIGNACIÓN (ASIG):
   Patrón: "Asignar funciones, a [NOMBRE], funciones en [DESTINO]"
   → No hay persona reemplazada

5. PRÓRROGA (PROR):
   Patrón: "Prorrogar el encargo/provisionalidad, a [NOMBRE]"
   → Extiende un nombramiento o encargo existente

6. REVOCACIÓN/ACLARACIÓN (MD):
   Patrón: "Revocar el Decreto No.X" o "Aclarar el Decreto No.X"
   → NO hay funcionarios, es modificación administrativa

7. COMISIÓN (C):
   Patrón: "Comisionar" o "Comision, a [NOMBRE]"

8. AUXILIAR AD HONOREM (NAADH):
   Patrón: "Nombrar auxiliar juridico ad-honorem"

=== REGLA CRÍTICA: DOS PERSONAS ===
En muchos decretos aparecen DOS personas:
1. PERSONA CON CÉDULA → ES el funcionario, VA en el array
2. PERSONA SIN CÉDULA (después de "en el cargo de [NOMBRE]") → NO es funcionario, va en persona_reemplazada

=== RESPUESTA JSON ===
{{
    "razonamiento": "PASO 1: Errores OCR corregidos: [lista]. PASO 2: Palabra clave '[X]' indica [TIPO]. PASO 3: Funcionario es [NOMBRE] con cédula [X]. PASO 4: [NOMBRE2] es persona reemplazada (sin cédula).",
    "numero_decreto": "{numero_decreto}",
    "anio": {anio},
    "fecha_decreto": "fecha encontrada o null",
    "codigo_novedad": "N/E/R/ASIG/PROR/MD/C/NAADH",
    "tipo_novedad": "Nombramiento/Encargo/Renuncia/Asignación/Prórroga/Modificación/Comisión",
    "funcionarios": [
        {{
            "cedula": "número SIN puntos",
            "nombre_completo": "NOMBRE APELLIDO",
            "cargo_actual": "solo en encargos",
            "cargo": "cargo nuevo o encargado",
            "codigo_cargo": "ej: 5OF",
            "grado": "ej: 06",
            "dependencia": "dependencia destino"
        }}
    ],
    "persona_reemplazada": "nombre de quien ocupaba el cargo (sin cédula)",
    "es_modificacion_decreto": false,
    "decreto_modificado": "número de decreto modificado si aplica",
    "resumen": "Decreto N-año: [Tipo] de [NOMBRE] como [cargo]"
}}
'''

if __name__ == "__main__":
    print(ANALISIS_PATRONES)
    print("\n" + "="*80)
    print("PROMPT OPTIMIZADO V3")
    print("="*80)
    print(PROMPT_OPTIMIZADO_V3)
