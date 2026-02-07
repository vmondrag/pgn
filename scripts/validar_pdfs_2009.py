"""
Script para validar la integridad de los PDFs del año 2009 con errores.
Verifica múltiples aspectos del archivo antes de intentar reprocesar.
"""
import os
from pathlib import Path

# Intentar importar librería PDF
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except:
    HAS_FITZ = False
    print("⚠️  PyMuPDF (fitz) no disponible")

try:
    from PyPDF2 import PdfReader
    HAS_PYPDF2 = True
except:
    HAS_PYPDF2 = False
    print("⚠️  PyPDF2 no disponible")

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except:
    HAS_PDFPLUMBER = False
    print("⚠️  pdfplumber no disponible")


def validar_pdf(pdf_path):
    """
    Valida la integridad de un archivo PDF.
    Retorna dict con resultados de validación.
    """
    resultado = {
        'archivo': os.path.basename(pdf_path),
        'ruta': pdf_path,
        'existe': False,
        'tamano_bytes': 0,
        'header_valido': False,
        'fitz_ok': False,
        'pypdf2_ok': False,
        'pdfplumber_ok': False,
        'paginas': 0,
        'errores': []
    }
    
    # 1. Verificar existencia
    if not os.path.exists(pdf_path):
        resultado['errores'].append("Archivo no existe")
        return resultado
    
    resultado['existe'] = True
    resultado['tamano_bytes'] = os.path.getsize(pdf_path)
    
    # 2. Verificar tamaño
    if resultado['tamano_bytes'] == 0:
        resultado['errores'].append("Archivo vacío (0 bytes)")
        return resultado
    
    # 3. Verificar header PDF
    try:
        with open(pdf_path, 'rb') as f:
            header = f.read(5)
            if header == b'%PDF-':
                resultado['header_valido'] = True
            else:
                resultado['errores'].append(f"Header inválido: {header}")
    except Exception as e:
        resultado['errores'].append(f"Error leyendo header: {e}")
    
    # 4. Intentar abrir con PyMuPDF (fitz)
    if HAS_FITZ:
        try:
            doc = fitz.open(pdf_path)
            resultado['fitz_ok'] = True
            resultado['paginas'] = len(doc)
            doc.close()
        except Exception as e:
            resultado['errores'].append(f"fitz error: {str(e)[:100]}")
    
    # 5. Intentar abrir con PyPDF2
    if HAS_PYPDF2:
        try:
            reader = PdfReader(pdf_path)
            resultado['pypdf2_ok'] = True
            if resultado['paginas'] == 0:
                resultado['paginas'] = len(reader.pages)
        except Exception as e:
            resultado['errores'].append(f"PyPDF2 error: {str(e)[:100]}")
    
    # 6. Intentar abrir con pdfplumber
    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                resultado['pdfplumber_ok'] = True
                if resultado['paginas'] == 0:
                    resultado['paginas'] = len(pdf.pages)
        except Exception as e:
            resultado['errores'].append(f"pdfplumber error: {str(e)[:100]}")
    
    return resultado


def validar_todos():
    """Valida todos los PDFs del 2009 con errores."""
    
    base_dir = Path(r"C:\temp\PNG_CERTIFICADO_V3\Decretos\2009")
    
    # Lista de archivos con error
    archivos_error = [
        "DECRETO 001-2009.pdf",
        "DECRETO 002-2009.pdf",
        "DECRETO 003 2009.pdf",
        "DECRETO 004-2009.pdf",
        "DECRETO 005-2009.pdf",
        "DECRETO 006-2009.pdf",
        "DECRETO 007-2009.pdf",
        "DECRETO 008-2009.pdf",
        "DECRETO 009-2009.pdf",
        "DECRETO 010-2009.pdf"
    ]
    
    print("=" * 100)
    print("VALIDACIÓN DE INTEGRIDAD DE PDFs DEL AÑO 2009")
    print("=" * 100)
    print(f"\nDirectorio: {base_dir}")
    print(f"Archivos a validar: {len(archivos_error)}\n")
    
    print(f"Librerías disponibles:")
    print(f"  - PyMuPDF (fitz): {'✓' if HAS_FITZ else '✗'}")
    print(f"  - PyPDF2: {'✓' if HAS_PYPDF2 else '✗'}")
    print(f"  - pdfplumber: {'✓' if HAS_PDFPLUMBER else '✗'}")
    print()
    
    resultados = []
    
    for archivo in archivos_error:
        pdf_path = base_dir / archivo
        resultado = validar_pdf(str(pdf_path))
        resultados.append(resultado)
    
    # Mostrar resultados
    print("=" * 100)
    print("RESULTADOS DE VALIDACIÓN")
    print("=" * 100)
    
    for i, r in enumerate(resultados, 1):
        print(f"\n[{i}/10] {r['archivo']}")
        print(f"  Existe: {'✓' if r['existe'] else '✗'}")
        print(f"  Tamaño: {r['tamano_bytes']:,} bytes ({r['tamano_bytes']/1024:.1f} KB)")
        print(f"  Header PDF: {'✓' if r['header_valido'] else '✗'}")
        print(f"  PyMuPDF (fitz): {'✓' if r['fitz_ok'] else '✗'}")
        print(f"  PyPDF2: {'✓' if r['pypdf2_ok'] else '✗'}")
        print(f"  pdfplumber: {'✓' if r['pdfplumber_ok'] else '✗'}")
        print(f"  Páginas detectadas: {r['paginas']}")
        
        if r['errores']:
            print(f"  ⚠️  Errores ({len(r['errores'])}):")
            for error in r['errores']:
                print(f"      - {error}")
    
    # Resumen
    print("\n" + "=" * 100)
    print("RESUMEN")
    print("=" * 100)
    
    total = len(resultados)
    existen = sum(1 for r in resultados if r['existe'])
    header_ok = sum(1 for r in resultados if r['header_valido'])
    fitz_ok = sum(1 for r in resultados if r['fitz_ok'])
    pypdf2_ok = sum(1 for r in resultados if r['pypdf2_ok'])
    pdfplumber_ok = sum(1 for r in resultados if r['pdfplumber_ok'])
    algun_ok = sum(1 for r in resultados if r['pypdf2_ok'] or r['pdfplumber_ok'])
    
    print(f"\nEstadísticas:")
    print(f"  Archivos existen: {existen}/{total}")
    print(f"  Header PDF válido: {header_ok}/{total}")
    print(f"  PyMuPDF puede abrir: {fitz_ok}/{total}")
    print(f"  PyPDF2 puede abrir: {pypdf2_ok}/{total}")
    print(f"  pdfplumber puede abrir: {pdfplumber_ok}/{total}")
    print(f"  Al menos una librería OK: {algun_ok}/{total}")
    
    # Estrategia recomendada
    print("\n" + "=" * 100)
    print("ESTRATEGIA RECOMENDADA")
    print("=" * 100)
    
    if fitz_ok == total:
        print("\n✓ ESTRATEGIA A: Reprocesar con PyMuPDF")
        print("  Todos los archivos pueden ser abiertos con PyMuPDF.")
        print("  El error anterior puede haber sido temporal.")
    elif algun_ok == total:
        print("\n✓ ESTRATEGIA B: Usar librería alternativa")
        print(f"  {pypdf2_ok} archivos se pueden abrir con PyPDF2")
        print(f"  {pdfplumber_ok} archivos se pueden abrir con pdfplumber")
        print("  Extraer como imágenes y aplicar OCR.")
    else:
        print("\n⚠️  ESTRATEGIA C: Reparación necesaria")
        archivos_problema = [r['archivo'] for r in resultados if not (r['pypdf2_ok'] or r['pdfplumber_ok'])]
        print(f"  {len(archivos_problema)} archivos no se pueden abrir con ninguna librería:")
        for a in archivos_problema:
            print(f"    - {a}")
        print("  Recomendación: Verificar archivos originales o usar herramientas de reparación.")
    
    print("\n" + "=" * 100)
    
    # Guardar reporte
    with open("reporte_validacion_2009.txt", "w", encoding='utf-8') as f:
        f.write("REPORTE DE VALIDACIÓN - PDFs AÑO 2009\n")
        f.write("=" * 100 + "\n\n")
        
        for r in resultados:
            f.write(f"{r['archivo']}\n")
            f.write(f"  Tamaño: {r['tamano_bytes']:,} bytes\n")
            f.write(f"  Header: {'OK' if r['header_valido'] else 'ERROR'}\n")
            f.write(f"  fitz: {'OK' if r['fitz_ok'] else 'ERROR'}\n")
            f.write(f"  PyPDF2: {'OK' if r['pypdf2_ok'] else 'ERROR'}\n")
            f.write(f"  pdfplumber: {'OK' if r['pdfplumber_ok'] else 'ERROR'}\n")
            f.write(f"  Páginas: {r['paginas']}\n")
            if r['errores']:
                f.write(f"  Errores:\n")
                for error in r['errores']:
                    f.write(f"    - {error}\n")
            f.write("\n")
    
    print(f"\n✓ Reporte guardado en: reporte_validacion_2009.txt")
    
    return resultados


if __name__ == "__main__":
    try:
        resultados = validar_todos()
        print("\n✓ Validación completada")
    except Exception as e:
        print(f"\n❌ Error durante validación: {e}")
        import traceback
        traceback.print_exc()
