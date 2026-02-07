"""
Graph View - Streamlit Component for Legal GraphRAG
====================================================
Interfaz visual para explorar el grafo de conocimiento legal.
Incluye visualización interactiva, búsqueda local/global y navegación.
"""

import streamlit as st
import json
import os
import sys

# Agregar path del módulo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from graph_engine import LegalGraphManager

# Configuración de la página
st.set_page_config(
    page_title="GraphRAG Legal - PGN",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
    }
    .stat-card {
        background: #1e293b;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        border: 1px solid #334155;
    }
    .stat-value {
        font-size: 2rem;
        font-weight: bold;
        color: #0ea5e9;
    }
    .stat-label {
        color: #94a3b8;
        font-size: 0.9rem;
    }
    .entity-card {
        background: #1e293b;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 4px solid #3b82f6;
    }
    .entity-decreto {
        border-left-color: #22c55e;
    }
    .entity-funcionario {
        border-left-color: #f59e0b;
    }
    .search-result {
        background: #334155;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    .community-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        background: rgba(124, 58, 237, 0.2);
        color: #a78bfa;
        border-radius: 20px;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_graph_manager(use_database: bool = True):
    """Cargar y cachear el grafo"""
    manager = LegalGraphManager()
    if use_database:
        # Cargar desde base de datos para sincronización en tiempo real
        manager.load_from_database()
    else:
        # Cargar desde archivos JSON (modo legacy)
        manager.load_graphrag_files()
    manager.detect_communities()
    return manager


def render_header():
    """Renderizar cabecera principal"""
    st.markdown("""
    <div class="main-header">
        <h1>🔗 GraphRAG Legal - PGN</h1>
        <p>Sistema de Análisis de Grafos de Conocimiento para Decretos de la Procuraduría General de la Nación</p>
    </div>
    """, unsafe_allow_html=True)


def render_stats(manager: LegalGraphManager):
    """Renderizar estadísticas del grafo"""
    summary = manager.get_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{summary.get('total_entities', 0):,}</div>
            <div class="stat-label">Entidades</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{summary.get('total_relationships', 0):,}</div>
            <div class="stat-label">Relaciones</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{summary.get('total_communities', 0):,}</div>
            <div class="stat-label">Comunidades</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        entity_types = summary.get('entity_types', {})
        decretos = entity_types.get('DECRETO', 0)
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{decretos:,}</div>
            <div class="stat-label">Decretos</div>
        </div>
        """, unsafe_allow_html=True)


def render_local_search(manager: LegalGraphManager):
    """Página de búsqueda local"""
    st.header("🔍 Búsqueda Local")
    st.markdown("Busca entidades específicas y explora sus conexiones directas en el grafo.")
    
    query = st.text_input(
        "Buscar por nombre, cédula o número de decreto:",
        placeholder="Ej: SIERRA, 70039458, 001"
    )
    
    depth = st.slider("Profundidad de búsqueda", 1, 3, 2)
    
    if query:
        with st.spinner("Buscando..."):
            results = manager.local_search(query, depth=depth)
            
        st.subheader(f"📊 Resultados: {results['total_matches']} coincidencias")
        
        # Matches directos
        if results['matches']:
            st.markdown("### 🎯 Coincidencias directas")
            for match in results['matches']:
                entity_class = "entity-decreto" if match['type'] == 'DECRETO' else "entity-funcionario"
                st.markdown(f"""
                <div class="entity-card {entity_class}">
                    <strong>{match['name']}</strong>
                    <span class="community-badge">{match['type']}</span>
                    <br><small>ID: {match['id']}</small>
                </div>
                """, unsafe_allow_html=True)
                
                # Mostrar propiedades en expander
                with st.expander("Ver detalles"):
                    st.json(match['properties'])
                    if match.get('source_file'):
                        st.markdown(f"📄 **Fuente:** `{os.path.basename(match['source_file'])}`")
                        
        # Entidades relacionadas
        if results['related_entities']:
            st.markdown("### 🔗 Entidades relacionadas")
            
            # Agrupar por tipo
            by_type = {}
            for entity in results['related_entities']:
                etype = entity['type']
                if etype not in by_type:
                    by_type[etype] = []
                by_type[etype].append(entity)
                
            for etype, entities in by_type.items():
                with st.expander(f"{etype} ({len(entities)})"):
                    for entity in entities[:10]:  # Limitar a 10
                        st.markdown(f"- **{entity['name']}** (distancia: {entity['distance']})")
                        
        # Relaciones
        if results['relationships']:
            st.markdown("### ↔️ Relaciones encontradas")
            for rel in results['relationships'][:10]:
                source_name = manager.entities.get(rel['source'], {})
                target_name = manager.entities.get(rel['target'], {})
                source_name = source_name.name if hasattr(source_name, 'name') else rel['source']
                target_name = target_name.name if hasattr(target_name, 'name') else rel['target']
                
                st.markdown(f"""
                <div class="search-result">
                    <strong>{source_name}</strong> 
                    → <span class="community-badge">{rel['type']}</span> → 
                    <strong>{target_name}</strong>
                </div>
                """, unsafe_allow_html=True)
                
        # Archivos fuente
        if results['source_files']:
            st.markdown("### 📂 Archivos fuente citados")
            for sf in results['source_files'][:5]:
                st.markdown(f"- `{os.path.basename(sf)}`")


def render_global_search(manager: LegalGraphManager):
    """Página de búsqueda global"""
    st.header("🌐 Búsqueda Global")
    st.markdown("Consultas transversales sobre temas y tendencias en los decretos.")
    
    query = st.text_input(
        "Consulta temática:",
        placeholder="Ej: encargos en la Oficina de Prensa, renuncias 2009"
    )
    
    if query:
        with st.spinner("Analizando comunidades..."):
            results = manager.global_search(query)
            
        # Estadísticas generales
        st.subheader("📊 Estadísticas del Grafo")
        stats = results['statistics']
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Distribución por tipo de novedad:**")
            novedad_data = stats.get('by_novedad', {})
            if novedad_data:
                import pandas as pd
                df = pd.DataFrame(list(novedad_data.items()), columns=['Código', 'Cantidad'])
                st.bar_chart(df.set_index('Código'))
                
        with col2:
            st.markdown("**Distribución por año:**")
            year_data = stats.get('by_year', {})
            if year_data:
                import pandas as pd
                df = pd.DataFrame(list(year_data.items()), columns=['Año', 'Decretos'])
                st.line_chart(df.set_index('Año'))
                
        # Comunidades relevantes
        if results['relevant_communities']:
            st.subheader("🏘️ Comunidades Relevantes")
            
            for comm in results['relevant_communities'][:5]:
                with st.expander(f"Comunidad #{comm['community_id']} - Score: {comm['score']} ({comm['dominant_type']})"):
                    st.markdown(f"**Tamaño:** {comm['size']} nodos")
                    st.markdown(f"**Resumen:** {comm['summary']}")
                    
                    if comm.get('relevant_nodes'):
                        st.markdown("**Entidades destacadas:**")
                        for node in comm['relevant_nodes']:
                            st.markdown(f"- {node.name} ({node.type})")
                            
        # Timeline
        if results['timeline']:
            st.subheader("📅 Línea Temporal de Decretos")
            
            for item in results['timeline'][:10]:
                st.markdown(f"""
                <div class="search-result">
                    <strong>{item['name']}</strong>
                    <span class="community-badge">{item.get('codigo_novedad', 'N/A')}</span>
                    <br>
                    <small>{item.get('resumen', 'Sin resumen')}</small>
                </div>
                """, unsafe_allow_html=True)


def render_graph_visualization(manager: LegalGraphManager):
    """Página de visualización del grafo"""
    st.header("🗺️ Visualización del Grafo")
    
    graph_data = manager.get_graph_data_for_visualization()
    
    st.info(f"""
    📊 **Grafo cargado:** {graph_data['stats']['total_nodes']} nodos, 
    {graph_data['stats']['total_edges']} aristas
    """)
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        filter_type = st.multiselect(
            "Filtrar por tipo de entidad:",
            ['DECRETO', 'FUNCIONARIO', 'UNIDAD'],
            default=['DECRETO', 'FUNCIONARIO']
        )
    with col2:
        max_nodes = st.slider("Máximo de nodos a mostrar:", 10, 200, 50)
        
    # Filtrar datos
    filtered_nodes = [n for n in graph_data['nodes'] if n['type'] in filter_type][:max_nodes]
    node_ids = {n['id'] for n in filtered_nodes}
    filtered_edges = [e for e in graph_data['edges'] if e['source'] in node_ids and e['target'] in node_ids]
    
    st.markdown(f"**Mostrando:** {len(filtered_nodes)} nodos, {len(filtered_edges)} aristas")
    
    # Intentar usar pyvis si está disponible
    try:
        from pyvis.network import Network
        import tempfile
        
        net = Network(height="600px", width="100%", bgcolor="#0f172a", font_color="white")
        net.barnes_hut()
        
        # Colores por tipo
        colors = {
            'DECRETO': '#22c55e',
            'FUNCIONARIO': '#f59e0b',
            'UNIDAD': '#3b82f6'
        }
        
        for node in filtered_nodes:
            net.add_node(
                node['id'],
                label=node['label'],
                color=colors.get(node['type'], '#94a3b8'),
                size=node['size'],
                title=f"{node['type']}: {node['label']}"
            )
            
        for edge in filtered_edges:
            net.add_edge(
                edge['source'],
                edge['target'],
                title=edge.get('label', ''),
                color='#475569'
            )
            
        # Guardar y mostrar
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as f:
            net.save_graph(f.name)
            with open(f.name, 'r', encoding='utf-8') as html_file:
                html_content = html_file.read()
            st.components.v1.html(html_content, height=650)
            
    except ImportError:
        st.warning("⚠️ Para visualización interactiva, instala: `pip install pyvis`")
        
        # Fallback: mostrar como tabla
        st.markdown("### 📋 Lista de Nodos")
        import pandas as pd
        df = pd.DataFrame(filtered_nodes)
        st.dataframe(df[['label', 'type', 'size']], use_container_width=True)
        
        st.markdown("### 🔗 Lista de Aristas")
        df_edges = pd.DataFrame(filtered_edges)
        if not df_edges.empty:
            st.dataframe(df_edges, use_container_width=True)


def render_entity_explorer(manager: LegalGraphManager):
    """Explorador de entidades individual"""
    st.header("📋 Explorador de Entidades")
    
    # Selector de tipo
    entity_type = st.selectbox(
        "Tipo de entidad:",
        ['DECRETO', 'FUNCIONARIO', 'UNIDAD']
    )
    
    # Filtrar entidades por tipo
    entities = [e for e in manager.entities.values() if e.type == entity_type]
    
    st.markdown(f"**{len(entities)} entidades de tipo {entity_type}**")
    
    # Selector de entidad
    entity_names = {e.name: e.id for e in entities}
    selected_name = st.selectbox(
        "Seleccionar entidad:",
        list(entity_names.keys())[:100]  # Limitar para rendimiento
    )
    
    if selected_name:
        entity_id = entity_names[selected_name]
        details = manager.get_entity_details(entity_id)
        
        if details:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"### {details['name']}")
                st.markdown(f"**Tipo:** {details['type']}")
                st.markdown(f"**Conexiones:** {details['degree']} relaciones")
                
                st.markdown("**Propiedades:**")
                st.json(details['properties'])
                
            with col2:
                if details['relationships']:
                    st.markdown("### 🔗 Relaciones")
                    for rel in details['relationships'][:10]:
                        direction = "→" if rel['direction'] == 'outgoing' else "←"
                        st.markdown(f"""
                        {direction} **{rel['type']}** {direction}
                        {rel['entity']['name']}
                        """)
                        
            # Enlace al PDF si existe
            archivo = details['properties'].get('archivo')
            if archivo and os.path.exists(archivo):
                st.markdown("---")
                st.markdown(f"📄 **Archivo fuente:** `{os.path.basename(archivo)}`")


def main():
    """Función principal de la aplicación"""
    
    # Cargar grafo
    manager = get_graph_manager()
    
    # Sidebar
    with st.sidebar:
        st.image("https://www.procuraduria.gov.co/portal/media/logo-pgn.png", width=200)
        st.title("📊 Navegación")
        
        page = st.radio(
            "Seleccionar vista:",
            ["🏠 Inicio", "🔍 Búsqueda Local", "🌐 Búsqueda Global", 
             "🗺️ Visualización", "📋 Explorador"]
        )
        
        st.markdown("---")
        st.markdown("### ℹ️ Información")
        summary = manager.get_summary()
        st.markdown(f"- **Entidades:** {summary.get('total_entities', 0):,}")
        st.markdown(f"- **Relaciones:** {summary.get('total_relationships', 0):,}")
        st.markdown(f"- **Comunidades:** {summary.get('total_communities', 0):,}")
        
        st.markdown("---")
        if st.button("🔄 Recargar Grafo"):
            st.cache_resource.clear()
            st.rerun()
            
    # Contenido principal según página
    if "Inicio" in page:
        render_header()
        render_stats(manager)
        
        st.markdown("---")
        st.markdown("""
        ### 🚀 Cómo usar este sistema
        
        1. **Búsqueda Local** - Encuentra funcionarios o decretos específicos y explora sus conexiones
        2. **Búsqueda Global** - Analiza tendencias y patrones en todos los decretos
        3. **Visualización** - Explora el grafo de manera interactiva
        4. **Explorador** - Navega por entidades individuales
        """)
        
    elif "Búsqueda Local" in page:
        render_local_search(manager)
        
    elif "Búsqueda Global" in page:
        render_global_search(manager)
        
    elif "Visualización" in page:
        render_graph_visualization(manager)
        
    elif "Explorador" in page:
        render_entity_explorer(manager)


if __name__ == "__main__":
    main()
