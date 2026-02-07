import fitz  # PyMuPDF
import os

# Definir los archivos a procesar
archivos = {
    "2023": {
        "carpeta": r"c:\temp\PNG_CERTIFICADO_V3\Decretos\RESOLUCIONES -2023",
        "archivos": [
            "RESOLUCION 006 DE 11 DE ENERO DE 2023.pdf",
            "RESOLUCION 030 DE 27 DE ENERO DE 2023.pdf",
            "RESOLUCION 041 DE 1 DE FEBRERO DE 2023.pdf",
            "RESOLUCION 049 DE 08 DE FEBRERO DE 2023.pdf",
            "RESOLUCION 061 DE 16 DE FEBRERO DE 2023.pdf",
            "NIDIA MARLENY DELGADO QUITIAN Y OTROS E 0210.pdf",
            "MELISSA DIAZ RAMOS C 0447.pdf"
        ]
    },
    "2024": {
        "carpeta": r"c:\temp\PNG_CERTIFICADO_V3\Decretos\RESOLUCIONES 2024",
        "archivos": [
            "RESOLUCION 001 DE 02 DE ENERO DE 2024 LUZ ESPERANZA FORERO DE SILVA.pdf",
            "RESOLUCION 002 DE 02 DE ENERO DE 2024 JOSE MARTIN ESPITIA RIAÑO.pdf",
            "RESOLUCION 010 DE 05 DE ENERO DE 2024 DEISY JANETH BARRIENTO PEREZ.pdf",
            "RESOLUCION 029 DE 30 DE ENERO DE 2024 GLORIA STELLA BELTRAN ROMERO.pdf",
            "RESOLUCION 031 DE 05 DE FEBRERO DE 2024.pdf",
            "RESOLUCION 032 DE 05 DE FEBRERO DE 2024.pdf",
            "RESOLUCION 319 DE 19 DE JULIO DE 2024.pdf"
        ]
    },
    "2025": {
        "carpeta": r"c:\temp\PNG_CERTIFICADO_V3\Decretos\RESOLUCIONES 2025",
        "archivos": [
            "RESOLUCION 001 DE 02 DE ENERO DE 2025.pdf",
            "RESOLUCION 005 DE 29 DE ENERO DE 2025.pdf",
            "RESOLUCION 010 DE 30 DE ENERO DE 2025 (002).pdf",
            "RESOLUCION 017 DE 13 DE ENERO DE 2025 GUILLERMO ALFREDO MEDINA RAMÍREZ.pdf",
            "RESOLUCION 020 DE 15 DE ENERO DE 2025 ANDREA LILIANA OSPINA BEJARANO.pdf",
            "RESOLUCION 025 DE 11 DE FEBRERO DE 2025.pdf"
        ]
    }
}

def analizar_tipo_novedad(texto):
    """Analiza el texto para determinar el tipo de novedad"""
    texto_lower = texto.lower()
    
    if "vacaciones" in texto_lower:
        return "VACACIONES"
    elif "licencia no remunerada" in texto_lower or "licencia ordinaria" in texto_lower:
        return "LICENCIA NO REMUNERADA"
    elif "licencia remunerada" in texto_lower:
        return "LICENCIA REMUNERADA"
    elif "licencia de maternidad" in texto_lower:
        return "LICENCIA DE MATERNIDAD"
    elif "licencia de paternidad" in texto_lower:
        return "LICENCIA DE PATERNIDAD"
    elif "licencia por luto" in texto_lower or "licencia de luto" in texto_lower:
        return "LICENCIA POR LUTO"
    elif "licencia" in texto_lower:
        return "LICENCIA (OTRO TIPO)"
    elif "encargo" in texto_lower:
        return "ENCARGO"
    elif "comision" in texto_lower or "comisión" in texto_lower:
        return "COMISION"
    elif "incapacidad" in texto_lower:
        return "INCAPACIDAD"
    elif "permiso" in texto_lower:
        return "PERMISO"
    elif "traslado" in texto_lower:
        return "TRASLADO"
    elif "nombramiento" in texto_lower:
        return "NOMBRAMIENTO"
    elif "retiro" in texto_lower or "renuncia" in texto_lower:
        return "RETIRO/RENUNCIA"
    elif "prima" in texto_lower:
        return "PRIMA"
    elif "bonificacion" in texto_lower or "bonificación" in texto_lower:
        return "BONIFICACION"
    else:
        return "NO IDENTIFICADO"

def extraer_texto_pdf(ruta_pdf):
    """Extrae texto de un PDF usando PyMuPDF"""
    try:
        doc = fitz.open(ruta_pdf)
        num_paginas = len(doc)
        texto_completo = ""
        
        for pagina in doc:
            texto_completo += pagina.get_text()
        
        doc.close()
        return num_paginas, texto_completo
    except Exception as e:
        return 0, f"ERROR: {str(e)}"

# Procesar todos los archivos
print("=" * 100)
print("EXTRACCION DE TEXTO DE RESOLUCIONES PDF")
print("=" * 100)

for año, datos in archivos.items():
    print(f"\n{'#' * 100}")
    print(f"# CARPETA {año}")
    print(f"{'#' * 100}")
    
    carpeta = datos["carpeta"]
    
    for archivo in datos["archivos"]:
        ruta_completa = os.path.join(carpeta, archivo)
        
        print(f"\n{'-' * 100}")
        print(f"ARCHIVO: {archivo}")
        print(f"RUTA: {ruta_completa}")
        print(f"{'-' * 100}")
        
        if not os.path.exists(ruta_completa):
            print(f"[!] ARCHIVO NO ENCONTRADO")
            continue
        
        num_paginas, texto = extraer_texto_pdf(ruta_completa)
        
        if texto.startswith("ERROR"):
            print(f"[!] {texto}")
            continue
        
        tipo_novedad = analizar_tipo_novedad(texto)
        
        print(f"PAGINAS: {num_paginas}")
        print(f"TIPO DE NOVEDAD DETECTADO: {tipo_novedad}")
        print(f"\nTEXTO EXTRAIDO (primeros 3000 caracteres):")
        print("." * 50)
        print(texto[:3000])
        print("." * 50)
        if len(texto) > 3000:
            print(f"[... {len(texto) - 3000} caracteres adicionales omitidos ...]")

print(f"\n{'=' * 100}")
print("EXTRACCION COMPLETADA")
print("=" * 100)
