"""
Legal GraphRAG Application - Main Entry Point
==============================================
Aplicación principal que integra el sistema GraphRAG con Flask API.
"""

import os
import sys

# Configurar encoding UTF-8 para Windows (soporte de emojis en consola)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Agregar path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_streamlit():
    """Ejecutar aplicación Streamlit"""
    import subprocess
    app_path = os.path.join(os.path.dirname(__file__), 'graph_view.py')
    subprocess.run(['streamlit', 'run', app_path, '--server.port', '8501'])


def run_flask(use_reloader=True):
    """Ejecutar API Flask existente

    Args:
        use_reloader: Si True, usa el reloader de Flask (solo en thread principal)
    """
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from app_novedades import app
    # use_reloader=False cuando corre en thread secundario para evitar error de signal
    app.run(debug=True, port=5000, host='0.0.0.0', use_reloader=use_reloader)


def main():
    """Menú principal"""
    print("=" * 60)
    print("LEGAL GRAPHRAG - PROCURADURÍA GENERAL DE LA NACIÓN")
    print("=" * 60)
    print()
    print("Opciones disponibles:")
    print("  1. Iniciar GraphRAG UI (Streamlit - Puerto 8501)")
    print("  2. Iniciar API Novedades (Flask - Puerto 5000)")
    print("  3. Ejecutar ambos servicios")
    print("  4. Prueba rápida del motor de grafos")
    print()
    
    choice = input("Seleccione opción [1-4]: ").strip()
    
    if choice == '1':
        print("\n🚀 Iniciando Streamlit GraphRAG en http://localhost:8501")
        run_streamlit()
        
    elif choice == '2':
        print("\n🚀 Iniciando Flask API en http://localhost:5000")
        run_flask()
        
    elif choice == '3':
        import threading
        print("\n🚀 Iniciando ambos servicios...")
        # use_reloader=False para evitar error: "signal only works in main thread"
        flask_thread = threading.Thread(target=lambda: run_flask(use_reloader=False), daemon=True)
        flask_thread.start()
        run_streamlit()
        
    elif choice == '4':
        print("\n🔍 Ejecutando prueba del motor de grafos...")
        from graph_engine import LegalGraphManager
        
        manager = LegalGraphManager()
        count = manager.load_graphrag_files(limit=50)
        print(f"✅ Cargados {count} archivos")
        
        communities = manager.detect_communities()
        print(f"✅ Detectadas {len(communities)} comunidades")
        
        # Prueba búsqueda local
        results = manager.local_search('SIERRA')
        print(f"✅ Búsqueda 'SIERRA': {results['total_matches']} resultados")
        
        # Prueba búsqueda global
        global_results = manager.global_search('encargo')
        print(f"✅ Búsqueda global 'encargo': {len(global_results['relevant_communities'])} comunidades relevantes")
        
        print("\n📊 Resumen del grafo:")
        summary = manager.get_summary()
        print(f"  - Entidades: {summary['total_entities']}")
        print(f"  - Relaciones: {summary['total_relationships']}")
        print(f"  - Por tipo: {summary.get('entity_types', {})}")
        
    else:
        print("Opción no válida")


if __name__ == '__main__':
    main()
