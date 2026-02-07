"""
Script para reprocesar los archivos del 2009 que originalmente tuvieron ERROR_NO_FITZ.
La validación mostró que todos pueden abrirse con PyMuPDF, por lo que simplemente
los reprocesamos con el script extract_decretos.py normal.
"""
import subprocess
import time
from pathlib import Path

def reprocesar_2009():
    """Reprocesa los 10 archivos del 2009 con error."""
    
    base_dir = Path(r"C:\temp\PNG_CERTIFICADO_V3")
    decretos_dir = base_dir / "Decretos" / "2009"
    output_dir = base_dir / "output_2009_hybrid"
    
    # Lista de archivos a reprocesar
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
    
    print("=" * 80)
    print("REPROCESAMIENTO DE ARCHIVOS DEL AÑO 2009")
    print("=" * 80)
    print(f"\nDirectorio de entrada: {decretos_dir}")
    print(f"Directorio de salida: {output_dir}")
    print(f"Archivos a reprocesar: {len(archivos_error)}\n")
    
    print("NOTA: Como los archivos 001-010 están al inicio del directorio,")
    print("vamos a ejecutar extract_decretos.py con --limit 10 para procesar solo estos.\n")
    
    # Ejecutar extract_decretos.py
    comando = [
        "python",
        "extract_decretos.py",
        "--dir-in",
        str(decretos_dir),
        "--llm",
        "gpt-oss:20b-cloud",
        "--output",
        str(output_dir),
        "--limit",
        "15"  # Procesar los primeros 15 para asegurar que incluye los 10 con error
    ]
    
    print("Comando a ejecutar:")
    print(" ".join(comando))
    print("\nIniciando procesamiento...\n")
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
            print(f"\n✅ Procesamiento completado exitosamente")
            print(f"⏱️  Tiempo total: {tiempo_total/60:.1f} minutos")
            
            # Mostrar últimas líneas de output
            output_lines = resultado.stdout.strip().split('\n')
            print(f"\n📋 Últimas líneas del output:")
            for line in output_lines[-10:]:
                print(f"   {line}")
        else:
            print(f"\n❌ Error en el procesamiento (código: {resultado.returncode})")
            print(f"\nSTDERR:")
            print(resultado.stderr)
        
        # Mostrar stdout completo si es corto
        if len(resultado.stdout) < 2000:
            print(f"\nOutput completo:")
            print(resultado.stdout)
        
    except subprocess.TimeoutExpired:
        print("\n⏱️  Timeout: El procesamiento tomó más de 30 minutos")
    except Exception as e:
        print(f"\n❌ Excepción durante procesamiento: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("Verificando resultados...")
    print("=" * 80)
    
    # Verificar archivos procesados
    graphrag_dir = output_dir / "graphrag"
    if graphrag_dir.exists():
        procesados = list(graphrag_dir.glob("*.graphrag.json"))
        print(f"\n✓ Total de archivos .graphrag.json en output: {len(procesados)}")
        
        # Verificar archivos específicos
        archivos_encontrados = []
        for archivo_error in archivos_error:
            base_name = archivo_error.replace('.pdf', '')
            archivo_json = graphrag_dir / f"{base_name}.graphrag.json"
            if archivo_json.exists():
                archivos_encontrados.append(archivo_error)
        
        print(f"✓ Archivos objetivo procesados: {len(archivos_encontrados)}/10")
        
        if archivos_encontrados:
            print(f"\n Archivos procesados:")
            for a in archivos_encontrados:
                print(f"   ✓ {a}")
        
        faltantes = [a for a in archivos_error if a not in archivos_encontrados]
        if faltantes:
            print(f"\n⚠️  Archivos aún faltantes: {len(faltantes)}")
            for a in faltantes:
                print(f"   ✗ {a}")
    else:
        print(f"\n⚠️  Directorio graphrag no existe: {graphrag_dir}")
    
    print("\n" + "=" * 80)
    print("✅ Reprocesamiento del año 2009 finalizado")
    print("=" * 80)


if __name__ == "__main__":
    reprocesar_2009()
