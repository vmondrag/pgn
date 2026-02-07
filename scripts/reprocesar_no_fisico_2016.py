"""
Script para reprocesar los archivos "NO FISICO" del 2016 que tuvieron ERROR_OCR.
Utiliza parámetros optimizados para mejorar el éxito del OCR.
"""
import subprocess
import time
from pathlib import Path

def reprocesar_no_fisico_2016():
    """Reprocesa los 2 archivos NO FISICO del 2016."""
    
    base_dir = Path(r"C:\temp\PNG_CERTIFICADO_V3")
    decretos_dir = base_dir / "Decretos" / "2016"
    output_dir = base_dir / "output_2016_hybrid"
    
    # Archivos específicos a reprocesar
    archivos_error = [
        "NO FISICO DECRETO 4694-4698-2016.pdf",
        "NO FISICO DECRETO 2675-2676-2016.pdf"
    ]
    
    print("=" * 80)
    print("REPROCESAMIENTO DE ARCHIVOS 'NO FISICO' DEL AÑO 2016")
    print("=" * 80)
    print(f"\nDirectorio de entrada: {decretos_dir}")
    print(f"Directorio de salida: {output_dir}")
    print(f"\nArchivos a reprocesar:")
    for archivo in archivos_error:
        print(f"  - {archivo}")
    
    print("\n📋 PARÁMETROS OPTIMIZADOS:")
    print("  - Modelo LLM: gpt-oss:20b-cloud")
    print("  - Se usará DPI 150 (óptimo para NIM PaddleOCR)")
    print("  - Modo preprocesamiento: grayscale (configurado en script)")
    print("  - Timeout OCR: 120s → 300s (modificación en extract_decretos.py)")
    
    # Como extract_decretos.py procesa todo el directorio,
    # vamos a ejecutarlo y dejará que salte los ya procesados
    comando = [
        "python",
        "extract_decretos.py",
        "--dir-in",
        str(decretos_dir),
        "--llm",
        "gpt-oss:20b-cloud"
    ]
    
    print("\n🔧 Comando a ejecutar:")
    print(" ".join(comando))
    print("\n⚠️  NOTA: El script procesará TODO el directorio 2016, pero saltará")
    print("   automáticamente los archivos ya procesados (resume mode).")
    print("   Solo se procesarán los 2 archivos NO FISICO con error.")
    
    print("\n" + "=" * 80)
    print("Iniciando procesamiento...")
    print("=" * 80)
    
    try:
        inicio = time.time()
        
        resultado = subprocess.run(
            comando,
            cwd=str(base_dir),
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutos
        )
        
        fin = time.time()
        tiempo_total = fin - inicio
        
        print("\n" + "=" * 80)
        print("RESULTADO DEL PROCESAMIENTO")
        print("=" * 80)
        
        if resultado.returncode == 0:
            print(f"\n✅ Procesamiento completado")
            print(f"⏱️  Tiempo total: {tiempo_total/60:.1f} minutos")
        else:
            print(f"\n❌ Error en el procesamiento (código: {resultado.returncode})")
        
        # Mostrar output relevante
        if resultado.stdout:
            output_lines = resultado.stdout.strip().split('\n')
            print(f"\n📋 Output del procesamiento:")
            # Buscar líneas relevantes
            for line in output_lines:
                if 'NO FISICO' in line or 'ERROR' in line or 'OK:' in line or 'Total procesados' in line:
                    print(f"   {line}")
        
        if resultado.stderr and len(resultado.stderr) > 0:
            print(f"\n⚠️  STDERR:")
            print(resultado.stderr[:500])
        
    except subprocess.TimeoutExpired:
        print("\n⏱️  Timeout: El procesamiento tomó más de 30 minutos")
    except Exception as e:
        print(f"\n❌ Excepción: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("Verificando resultados...")
    print("=" * 80)
    
    # Verificar archivos procesados
    graphrag_dir = output_dir / "graphrag"
    if graphrag_dir.exists():
        total_procesados = len(list(graphrag_dir.glob("*.graphrag.json")))
        print(f"\n✓ Total de archivos en output/graphrag: {total_procesados}")
        
        # Verificar archivos específicos
        archivos_encontrados = []
        for archivo_error in archivos_error:
            base_name = archivo_error.replace('.pdf', '')
            archivo_json = graphrag_dir / f"{base_name}.graphrag.json"
            if archivo_json.exists():
                archivos_encontrados.append(archivo_error)
                # Verificar tamaño
                tamano = archivo_json.stat().st_size
                print(f"\n✓ {archivo_error}")
                print(f"  Archivo output: {archivo_json.name}")
                print(f"  Tamaño: {tamano:,} bytes ({tamano/1024:.1f} KB)")
        
        exitosos = len(archivos_encontrados)
        print(f"\n📊 Resultado: {exitosos}/2 archivos procesados exitosamente")
        
        faltantes = [a for a in archivos_error if a not in archivos_encontrados]
        if faltantes:
            print(f"\n⚠️  Archivos aún con error:")
            for a in faltantes:
                print(f"   ✗ {a}")
        else:
            print(f"\n🎉 ¡TODOS LOS ARCHIVOS PROCESADOS EXITOSAMENTE!")
    else:
        print(f"\n⚠️  Directorio graphrag no existe: {graphrag_dir}")
    
    print("\n" + "=" * 80)
    print("✅ Reprocesamiento de archivos 'NO FISICO' 2016 finalizado")
    print("=" * 80)
    
    return exitosos == 2


if __name__ == "__main__":
    exito = reprocesar_no_fisico_2016()
    if exito:
        print("\n✅ Todos los archivos fueron reprocesados exitosamente")
    else:
        print("\n⚠️  Algunos archivos aún tienen errores")
