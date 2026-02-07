"""
Script de Verificación Completa del Sistema
Fecha: 2026-01-18
Autor: Sistema de Validación Automática

Valida que todos los PDFs tengan:
1. Archivo de output (.graphrag.json)
2. Registro en la base de datos novedades_pgn.db

Genera reporte de inconsistencias en formato Markdown.
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Configuración
BASE_DIR = Path(r"C:\temp\PNG_CERTIFICADO_V3")
DECRETOS_DIR = BASE_DIR / "Decretos"
DB_PATH = BASE_DIR / "novedades_pgn.db"
LOG_FILE = BASE_DIR / "log_verificacion_pdf_salida_bd.md"

# Rangos de años
ANIOS_DECRETOS = list(range(2009, 2026))  # 2009-2025
ANIOS_RESOLUCIONES = [2023, 2024, 2025]

class VerificadorSistema:
    """Clase para verificar la integridad del sistema de procesamiento."""
    
    def __init__(self, test_mode=False, test_limit=10):
        self.test_mode = test_mode
        self.test_limit = test_limit
        self.inconsistencias = []
        self.estadisticas = {
            'total_pdfs': 0,
            'con_output': 0,
            'sin_output': 0,
            'con_bd': 0,
            'sin_bd': 0,
            'output_sin_bd': 0,
            'bd_sin_output': 0,
            'completos': 0
        }
        
    def conectar_bd(self):
        """Conecta a la base de datos."""
        return sqlite3.connect(DB_PATH)
    
    def verificar_decreto(self, pdf_path: Path, anio: int) -> Dict:
        """Verifica un decreto individual."""
        resultado = {
            'archivo': pdf_path.name,
            'ruta': str(pdf_path),
            'anio': anio,
            'existe_pdf': pdf_path.exists(),
            'existe_output': False,
            'existe_bd': False,
            'output_path': None,
            'errores': []
        }
        
        if not resultado['existe_pdf']:
            resultado['errores'].append("PDF no existe")
            return resultado
        
        # Verificar output
        base_name = pdf_path.stem
        output_dir = BASE_DIR / f"output_{anio}_hybrid" / "graphrag"
        output_file = output_dir / f"{base_name}.graphrag.json"
        
        resultado['output_path'] = str(output_file)
        resultado['existe_output'] = output_file.exists()
        
        # Verificar en BD
        conn = self.conectar_bd()
        cursor = conn.cursor()
        
        # Buscar en tabla decretos por archivo_origen
        cursor.execute("""
            SELECT id, numero_decreto, fecha_decreto, estado_procesamiento
            FROM decretos
            WHERE archivo_origen LIKE ? OR archivo_origen LIKE ?
        """, (f"%{pdf_path.name}", f"%{base_name}%"))
        
        registro_bd = cursor.fetchone()
        resultado['existe_bd'] = registro_bd is not None
        
        if registro_bd:
            resultado['id_bd'] = registro_bd[0]
            resultado['numero_decreto'] = registro_bd[1]
            resultado['fecha_decreto'] = registro_bd[2]
            resultado['estado_bd'] = registro_bd[3]
        
        conn.close()
        
        # Detectar inconsistencias
        if resultado['existe_output'] and not resultado['existe_bd']:
            resultado['errores'].append("Tiene output pero NO está en BD")
            self.inconsistencias.append(resultado.copy())
        elif not resultado['existe_output'] and resultado['existe_bd']:
            resultado['errores'].append("Está en BD pero NO tiene output")
            self.inconsistencias.append(resultado.copy())
        elif not resultado['existe_output'] and not resultado['existe_bd']:
            resultado['errores'].append("NO tiene output NI está en BD")
            self.inconsistencias.append(resultado.copy())
        
        return resultado
    
    def verificar_resolucion(self, pdf_path: Path, anio: int) -> Dict:
        """Verifica una resolución individual."""
        resultado = {
            'archivo': pdf_path.name,
            'ruta': str(pdf_path),
            'anio': anio,
            'existe_pdf': pdf_path.exists(),
            'existe_output': False,
            'existe_bd': False,
            'output_path': None,
            'errores': []
        }
        
        if not resultado['existe_pdf']:
            resultado['errores'].append("PDF no existe")
            return resultado
        
        # Verificar output
        base_name = pdf_path.stem
        output_dir = BASE_DIR / f"output_res_{anio}" / "graphrag"
        output_file = output_dir / f"{base_name}.graphrag.json"
        
        resultado['output_path'] = str(output_file)
        resultado['existe_output'] = output_file.exists()
        
        # Verificar en BD (tabla resoluciones)
        conn = self.conectar_bd()
        cursor = conn.cursor()
        
        # Verificar si existe tabla resoluciones
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resoluciones'")
        if cursor.fetchone():
            cursor.execute("""
                SELECT id, numero_resolucion, fecha_resolucion, estado_procesamiento
                FROM resoluciones
                WHERE archivo_origen LIKE ? OR archivo_origen LIKE ?
            """, (f"%{pdf_path.name}", f"%{base_name}%"))
            
            registro_bd = cursor.fetchone()
            resultado['existe_bd'] = registro_bd is not None
            
            if registro_bd:
                resultado['id_bd'] = registro_bd[0]
                resultado['numero_resolucion'] = registro_bd[1]
                resultado['fecha_resolucion'] = registro_bd[2]
                resultado['estado_bd'] = registro_bd[3]
        
        conn.close()
        
        # Detectar inconsistencias
        if resultado['existe_output'] and not resultado['existe_bd']:
            resultado['errores'].append("Tiene output pero NO está en BD")
            self.inconsistencias.append(resultado.copy())
        elif not resultado['existe_output'] and resultado['existe_bd']:
            resultado['errores'].append("Está en BD pero NO tiene output")
            self.inconsistencias.append(resultado.copy())
        elif not resultado['existe_output'] and not resultado['existe_bd']:
            resultado['errores'].append("NO tiene output NI está en BD")
            self.inconsistencias.append(resultado.copy())
        
        return resultado
    
    def verificar_decretos_anio(self, anio: int) -> List[Dict]:
        """Verifica todos los decretos de un año."""
        print(f"  Verificando decretos del año {anio}...")
        
        decretos_dir = DECRETOS_DIR / str(anio)
        if not decretos_dir.exists():
            print(f"    ⚠️  Directorio no existe: {decretos_dir}")
            return []
        
        pdfs = list(decretos_dir.glob("*.pdf"))
        
        if self.test_mode:
            pdfs = pdfs[:self.test_limit]
            print(f"    🧪 Modo test: Solo {len(pdfs)} archivos")
        
        resultados = []
        for pdf in pdfs:
            resultado = self.verificar_decreto(pdf, anio)
            resultados.append(resultado)
            
            # Actualizar estadísticas
            self.estadisticas['total_pdfs'] += 1
            if resultado['existe_output']:
                self.estadisticas['con_output'] += 1
            else:
                self.estadisticas['sin_output'] += 1
            
            if resultado['existe_bd']:
                self.estadisticas['con_bd'] += 1
            else:
                self.estadisticas['sin_bd'] += 1
            
            if resultado['existe_output'] and resultado['existe_bd']:
                self.estadisticas['completos'] += 1
            
            if resultado['existe_output'] and not resultado['existe_bd']:
                self.estadisticas['output_sin_bd'] += 1
            elif not resultado['existe_output'] and resultado['existe_bd']:
                self.estadisticas['bd_sin_output'] += 1
        
        print(f"    ✓ Verificados: {len(resultados)} archivos")
        return resultados
    
    def verificar_resoluciones_anio(self, anio: int) -> List[Dict]:
        """Verifica todas las resoluciones de un año."""
        print(f"  Verificando resoluciones del año {anio}...")
        
        # El directorio tiene nombres diferentes
        if anio == 2023:
            res_dir = DECRETOS_DIR / "RESOLUCIONES -2023"
        else:
            res_dir = DECRETOS_DIR / f"RESOLUCIONES {anio}"
        
        if not res_dir.exists():
            print(f"    ⚠️  Directorio no existe: {res_dir}")
            return []
        
        pdfs = list(res_dir.glob("*.pdf"))
        
        if self.test_mode:
            pdfs = pdfs[:self.test_limit]
            print(f"    🧪 Modo test: Solo {len(pdfs)} archivos")
        
        resultados = []
        for pdf in pdfs:
            resultado = self.verificar_resolucion(pdf, anio)
            resultados.append(resultado)
            
            # Actualizar estadísticas
            self.estadisticas['total_pdfs'] += 1
            if resultado['existe_output']:
                self.estadisticas['con_output'] += 1
            else:
                self.estadisticas['sin_output'] += 1
            
            if resultado['existe_bd']:
                self.estadisticas['con_bd'] += 1
            else:
                self.estadisticas['sin_bd'] += 1
            
            if resultado['existe_output'] and resultado['existe_bd']:
                self.estadisticas['completos'] += 1
            
            if resultado['existe_output'] and not resultado['existe_bd']:
                self.estadisticas['output_sin_bd'] += 1
            elif not resultado['existe_output'] and resultado['existe_bd']:
                self.estadisticas['bd_sin_output'] += 1
        
        print(f"    ✓ Verificados: {len(resultados)} archivos")
        return resultados
    
    def generar_reporte_md(self):
        """Genera el reporte en formato Markdown."""
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write("# Log de Verificación: PDFs - Outputs - Base de Datos\n\n")
            f.write(f"**Fecha de verificación:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            if self.test_mode:
                f.write("> **🧪 MODO TEST:** Verificación limitada a {} archivos por año\n\n".format(self.test_limit))
            
            f.write("---\n\n")
            
            # Estadísticas generales
            f.write("## 📊 Estadísticas Generales\n\n")
            f.write(f"| Métrica | Cantidad | Porcentaje |\n")
            f.write(f"|---------|----------|------------|\n")
            f.write(f"| Total PDFs verificados | {self.estadisticas['total_pdfs']:,} | 100% |\n")
            f.write(f"| Con output | {self.estadisticas['con_output']:,} | {self.estadisticas['con_output']/max(self.estadisticas['total_pdfs'],1)*100:.2f}% |\n")
            f.write(f"| Sin output | {self.estadisticas['sin_output']:,} | {self.estadisticas['sin_output']/max(self.estadisticas['total_pdfs'],1)*100:.2f}% |\n")
            f.write(f"| Con registro en BD | {self.estadisticas['con_bd']:,} | {self.estadisticas['con_bd']/max(self.estadisticas['total_pdfs'],1)*100:.2f}% |\n")
            f.write(f"| Sin registro en BD | {self.estadisticas['sin_bd']:,} | {self.estadisticas['sin_bd']/max(self.estadisticas['total_pdfs'],1)*100:.2f}% |\n")
            f.write(f"| **Completos (output + BD)** | **{self.estadisticas['completos']:,}** | **{self.estadisticas['completos']/max(self.estadisticas['total_pdfs'],1)*100:.2f}%** |\n")
            f.write(f"\n")
            
            # Inconsistencias
            f.write("## ⚠️ Inconsistencias Detectadas\n\n")
            f.write(f"**Total de inconsistencias:** {len(self.inconsistencias)}\n\n")
            
            if self.estadisticas['output_sin_bd'] > 0:
                f.write(f"- **Output sin BD:** {self.estadisticas['output_sin_bd']} archivos tienen output pero NO están en la base de datos\n")
            if self.estadisticas['bd_sin_output'] > 0:
                f.write(f"- **BD sin output:** {self.estadisticas['bd_sin_output']} archivos están en BD pero NO tienen output\n")
            
            total_sin_ambos = self.estadisticas['sin_output'] - self.estadisticas['bd_sin_output']
            if total_sin_ambos > 0:
                f.write(f"- **Sin output ni BD:** {total_sin_ambos} archivos no tienen output NI están en BD\n")
            
            f.write("\n---\n\n")
            
            # Detalle de inconsistencias
            if self.inconsistencias:
                f.write("## 📋 Detalle de Inconsistencias\n\n")
                
                for i, inc in enumerate(self.inconsistencias, 1):
                    f.write(f"### {i}. {inc['archivo']}\n\n")
                    f.write(f"- **Año:** {inc['anio']}\n")
                    f.write(f"- **Archivo PDF:** {inc['ruta']}\n")
                    f.write(f"- **Output:** {'✓ Existe' if inc['existe_output'] else '✗ NO existe'}\n")
                    if inc. get('output_path'):
                        f.write(f"  - Ruta: `{inc['output_path']}`\n")
                    f.write(f"- **Base de Datos:** {'✓ Existe' if inc['existe_bd'] else '✗ NO existe'}\n")
                    if inc.get('id_bd'):
                        f.write(f"  - ID: {inc['id_bd']}\n")
                    f.write(f"- **Problemas:**\n")
                    for error in inc['errores']:
                        f.write(f"  - ⚠️ {error}\n")
                    f.write("\n")
            else:
                f.write("✅ **No se detectaron inconsistencias**\n\n")
            
            f.write("\n---\n\n")
            f.write("*Reporte generado automáticamente por 2026_01_18_verificaciones_full.py*\n")
    
    def ejecutar(self):
        """Ejecuta la verificación completa."""
        print("=" * 80)
        print("VERIFICACIÓN COMPLETA DEL SISTEMA")
        print("=" * 80)
        print(f"\nBase de datos: {DB_PATH}")
        print(f"Directorio base: {DECRETOS_DIR}")
        
        if self.test_mode:
            print(f"\n🧪 MODO TEST: Verificando solo {self.test_limit} archivos por año")
        
        print("\n" + "-" * 80)
        print("DECRETOS")
        print("-" * 80)
        
        for anio in ANIOS_DECRETOS:
            self.verificar_decretos_anio(anio)
        
        print("\n" + "-" * 80)
        print("RESOLUCIONES")
        print("-" * 80)
        
        for anio in ANIOS_RESOLUCIONES:
            self.verificar_resoluciones_anio(anio)
        
        print("\n" + "=" * 80)
        print("GENERANDO REPORTE")
        print("=" * 80)
        
        self.generar_reporte_md()
        
        print(f"\n✓ Reporte generado: {LOG_FILE}")
        print(f"\n📊 RESUMEN:")
        print(f"  Total verificados: {self.estadisticas['total_pdfs']:,}")
        print(f"  Completos: {self.estadisticas['completos']:,} ({self.estadisticas['completos']/max(self.estadisticas['total_pdfs'],1)*100:.2f}%)")
        print(f"  Inconsistencias: {len(self.inconsistencias)}")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    import sys
    
    # Detectar modo test
    test_mode = '--test' in sys.argv or '-t' in sys.argv
    
    verificador = VerificadorSistema(test_mode=test_mode, test_limit=10)
    verificador.ejecutar()
