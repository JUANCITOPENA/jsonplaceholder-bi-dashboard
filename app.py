import io
import requests
import pandas as pd
import plotly.express as px
import streamlit as st

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS
# ==============================================================================
st.set_page_config(
    page_title="Dashboard Analítico | JSONPlaceholder ETL",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 15px 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }
    @media (prefers-color-scheme: dark) {
        div[data-testid="stMetric"] {
            background-color: #1e2129;
            border: 1px solid #2e333f;
        }
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. PROCESO ETL (EXTRACCIÓN, TRANSFORMACIÓN Y CARGA CON CACHÉ)
# ==============================================================================
BASE_URL = "https://jsonplaceholder.typicode.com"

@st.cache_data(ttl=3600, show_spinner="Extrayendo y transformando datos desde las APIs...")
def run_etl_pipeline():
    """
    Descarga datos de Users, Posts y Comments, limpia estructuras anidadas,
    y construye tablas relacionales listas para análisis BI.
    """
    try:
        # --- EXTRACT ---
        res_users = requests.get(f"{BASE_URL}/users", timeout=10)
        res_posts = requests.get(f"{BASE_URL}/posts", timeout=10)
        res_comments = requests.get(f"{BASE_URL}/comments", timeout=10)

        res_users.raise_for_status()
        res_posts.raise_for_status()
        res_comments.raise_for_status()

        users_raw = res_users.json()
        posts_raw = res_posts.json()
        comments_raw = res_comments.json()

        # --- TRANSFORM ---
        # 1. Normalizar Usuarios (aplanar address y company)
        df_users = pd.json_normalize(users_raw)
        df_users = df_users.rename(columns={
            "id": "userId",
            "name": "user_name",
            "username": "username",
            "email": "user_email",
            "address.city": "city",
            "address.zipcode": "zipcode",
            "company.name": "company_name",
            "company.bs": "company_bs"
        })
        cols_users = [
            "userId", "user_name", "username", "user_email",
            "city", "company_name", "company_bs"
        ]
        df_users = df_users[cols_users].copy()

        # Limpieza básica de texto
        for col in ["user_name", "city", "company_name"]:
            df_users[col] = df_users[col].astype(str).str.strip()

        # 2. Limpiar Publicaciones
        df_posts = pd.DataFrame(posts_raw).rename(columns={
            "id": "postId",
            "title": "post_title",
            "body": "post_body"
        })
        df_posts["post_title"] = df_posts["post_title"].str.strip().str.capitalize()
        df_posts["post_length"] = df_posts["post_body"].str.len()

        # 3. Limpiar Comentarios
        df_comments = pd.DataFrame(comments_raw).rename(columns={
            "id": "commentId",
            "name": "comment_title",
            "email": "commenter_email",
            "body": "comment_body"
        })
        df_comments["comment_length"] = df_comments["comment_body"].str.len()

        # --- LOAD / RELACIÓN DE ENTIDADES ---
        # Conteo de comentarios por postId
        comments_per_post = (
            df_comments.groupby("postId", as_index=False)
            .agg(total_comments=("commentId", "count"))
        )

        # Unir Posts con Usuarios y conteo de Comentarios
        df_posts_enriched = (
            df_posts
            .merge(df_users, on="userId", how="left")
            .merge(comments_per_post, on="postId", how="left")
        )
        df_posts_enriched["total_comments"] = df_posts_enriched["total_comments"].fillna(0).astype(int)

        # Tabla maestra a nivel de Usuario (Métricas agregadas)
        user_metrics = (
            df_posts_enriched.groupby(
                ["userId", "user_name", "username", "user_email", "city", "company_name"],
                as_index=False
            )
            .agg(
                total_posts=("postId", "count"),
                total_comments=("total_comments", "sum"),
                avg_post_length=("post_length", "mean")
            )
        )
        user_metrics["avg_comments_per_post"] = (
            user_metrics["total_comments"] / user_metrics["total_posts"]
        ).round(2)
        user_metrics["avg_post_length"] = user_metrics["avg_post_length"].round(1)

        # Dataset completo de comentarios enriquecido (para exportación)
        df_comments_enriched = df_comments.merge(
            df_posts_enriched[["postId", "post_title", "userId", "user_name", "city", "company_name"]],
            on="postId",
            how="left"
        )

        return df_users, df_posts_enriched, df_comments_enriched, user_metrics, None

    except requests.exceptions.Timeout:
        return None, None, None, None, "Tiempo de espera agotado al conectar con JSONPlaceholder API."
    except requests.exceptions.HTTPError as e:
        return None, None, None, None, f"Error HTTP al consultar la API: {e}"
    except requests.exceptions.RequestException as e:
        return None, None, None, None, f"Error de conexión de red: {e}"
    except Exception as e:
        return None, None, None, None, f"Error inesperado durante el proceso ETL: {e}"

# ==============================================================================
# 3. FUNCIONES AUXILIARES DE EXPORTACIÓN
# ==============================================================================
@st.cache_data
def convert_df_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")

@st.cache_data
def convert_dfs_to_excel(df_users_summary: pd.DataFrame, df_posts: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_users_summary.to_excel(writer, sheet_name="Resumen_Usuarios", index=False)
        df_posts.to_excel(writer, sheet_name="Detalle_Publicaciones", index=False)
    return output.getvalue()

# ==============================================================================
# 4. EJECUCIÓN PRINCIPAL Y BARRA LATERAL
# ==============================================================================
df_users, df_posts, df_comments, df_user_summary, error_msg = run_etl_pipeline()

if error_msg:
    st.error(f"❌ Fallo en la carga de datos: {error_msg}")
    if st.button("🔄 Reintentar conexión"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

# --- SIDEBAR: FILTROS ---
st.sidebar.header("🎛️ Filtros de Segmentación")
st.sidebar.markdown("Filtra los indicadores y gráficos de forma dinámica:")

# Filtro de Ciudad
ciudades_disponibles = sorted(df_user_summary["city"].unique().tolist())
selected_cities = st.sidebar.multiselect(
    "🏙️ Ciudad",
    options=ciudades_disponibles,
    default=ciudades_disponibles
)

# Filtro de Empresa (dependiente de ciudades seleccionadas)
empresas_disponibles = sorted(
    df_user_summary[df_user_summary["city"].isin(selected_cities)]["company_name"].unique().tolist()
)
selected_companies = st.sidebar.multiselect(
    "🏢 Empresa",
    options=empresas_disponibles,
    default=empresas_disponibles
)

# Filtro de Usuario (dependiente de ciudad y empresa)
usuarios_disponibles = sorted(
    df_user_summary[
        (df_user_summary["city"].isin(selected_cities)) &
        (df_user_summary["company_name"].isin(selected_companies))
    ]["user_name"].unique().tolist()
)
selected_users = st.sidebar.multiselect(
    "👤 Usuario",
    options=usuarios_disponibles,
    default=usuarios_disponibles
)

# Filtro de Cantidad de Publicaciones
min_posts = int(df_user_summary["total_posts"].min())
max_posts = int(df_user_summary["total_posts"].max())

if min_posts < max_posts:
    post_range = st.sidebar.slider(
        "📝 Cantidad de Publicaciones por Usuario",
        min_value=min_posts,
        max_value=max_posts,
        value=(min_posts, max_posts)
    )
else:
    st.sidebar.info(f"📝 Todos los usuarios tienen exactamente **{min_posts}** publicaciones.")
    post_range = (min_posts, max_posts)

st.sidebar.divider()
if st.sidebar.button("🧹 Limpiar caché y actualizar API", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# --- APLICACIÓN DE FILTROS ---
filtered_users = df_user_summary[
    (df_user_summary["city"].isin(selected_cities)) &
    (df_user_summary["company_name"].isin(selected_companies)) &
    (df_user_summary["user_name"].isin(selected_users)) &
    (df_user_summary["total_posts"].between(post_range[0], post_range[1]))
].copy()

valid_user_ids = filtered_users["userId"].unique()
filtered_posts = df_posts[df_posts["userId"].isin(valid_user_ids)].copy()
filtered_comments = df_comments[df_comments["userId"].isin(valid_user_ids)].copy()

# ==============================================================================
# 5. ENCABEZADO Y KPIS PRINCIPALES
# ==============================================================================
st.title("📊 Dashboard Analítico de Usuarios, Publicaciones y Comentarios")
st.caption("Pipeline ETL automatizado consumiendo JSONPlaceholder REST API (`users`, `posts`, `comments`)")

if filtered_users.empty:
    st.warning("⚠️ No hay registros que coincidan con los filtros seleccionados. Ajusta los criterios en la barra lateral.")
    st.stop()

total_usuarios = len(filtered_users)
total_publicaciones = len(filtered_posts)
total_comentarios = len(filtered_comments)
promedio_comentarios = round(total_comentarios / total_publicaciones, 2) if total_publicaciones > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("👥 Total de Usuarios", f"{total_usuarios:,}")
col2.metric("📝 Total de Publicaciones", f"{total_publicaciones:,}")
col3.metric("💬 Total de Comentarios", f"{total_comentarios:,}")
col4.metric("📈 Promedio Comentarios / Post", f"{promedio_comentarios:.2f}")

st.divider()

# ==============================================================================
# 6. VISUALIZACIONES INTERACTIVAS (PLOTLY)
# ==============================================================================
row1_col1, row1_col2 = st.columns([1.3, 1])

with row1_col1:
    st.subheader("📊 Publicaciones y Comentarios por Usuario")
    df_bar = filtered_users.sort_values(by="total_comments", ascending=True)
    fig_bar = px.bar(
        df_bar,
        x=["total_posts", "total_comments"],
        y="user_name",
        orientation="h",
        barmode="group",
        labels={"value": "Cantidad", "user_name": "Usuario", "variable": "Métrica"},
        color_discrete_map={"total_posts": "#3b82f6", "total_comments": "#10b981"},
        height=420
    )
    fig_bar.for_each_trace(lambda t: t.update(name="Publicaciones" if t.name == "total_posts" else "Comentarios"))
    fig_bar.update_layout(margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h", y=1.08))
    st.plotly_chart(fig_bar, use_container_width=True)

with row1_col2:
    st.subheader("🥧 Distribución de Comentarios por Ciudad")
    df_pie = filtered_users.groupby("city", as_index=False)["total_comments"].sum()
    fig_pie = px.pie(
        df_pie,
        names="city",
        values="total_comments",
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Set2,
        height=420
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    fig_pie.update_layout(margin=dict(l=10, r=10, t=20, b=10), showlegend=False)
    st.plotly_chart(fig_pie, use_container_width=True)

row2_col1, row2_col2 = st.columns([1.3, 1])

with row2_col1:
    st.subheader("🔵 Dispersión: Extensión del Post vs. Comentarios")
    fig_scatter = px.scatter(
        filtered_posts,
        x="post_length",
        y="total_comments",
        color="city",
        size="total_comments",
        hover_data=["user_name", "post_title", "company_name"],
        labels={
            "post_length": "Longitud del Post (caracteres)",
            "total_comments": "Comentarios Recibidos",
            "city": "Ciudad"
        },
        height=380
    )
    fig_scatter.update_layout(margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig_scatter, use_container_width=True)

with row2_col2:
    st.subheader("🏆 Ranking de Usuarios Más Activos")
    ranking_df = (
        filtered_users[["user_name", "company_name", "total_posts", "total_comments", "avg_comments_per_post"]]
        .sort_values(by=["total_comments", "total_posts"], ascending=False)
        .reset_index(drop=True)
    )
    ranking_df.index = ranking_df.index + 1
    ranking_df.columns = ["Usuario", "Empresa", "Posts", "Comentarios", "Prom. Com/Post"]
    st.dataframe(ranking_df, use_container_width=True, height=340)

st.divider()

# ==============================================================================
# 7. TABLAS DINÁMICAS Y EXPORTACIÓN DE DATOS
# ==============================================================================
st.subheader("📑 Explorador de Datos Relacionales y Exportación")

tab1, tab2, tab3 = st.tabs([
    "👤 Resumen por Usuario",
    "📝 Detalle de Publicaciones",
    "📊 Tabla Dinámica (Ciudad vs. Empresa)"
])

with tab1:
    st.dataframe(
        filtered_users.rename(columns={
            "userId": "ID",
            "user_name": "Nombre",
            "username": "Alias",
            "user_email": "Correo",
            "city": "Ciudad",
            "company_name": "Empresa",
            "total_posts": "Publicaciones",
            "total_comments": "Comentarios",
            "avg_post_length": "Long. Media Post",
            "avg_comments_per_post": "Prom. Comentarios/Post"
        }),
        use_container_width=True,
        hide_index=True
    )

with tab2:
    st.dataframe(
        filtered_posts[["postId", "user_name", "city", "company_name", "post_title", "post_length", "total_comments"]].rename(columns={
            "postId": "Post ID",
            "user_name": "Autor",
            "city": "Ciudad",
            "company_name": "Empresa",
            "post_title": "Título de Publicación",
            "post_length": "Caracteres",
            "total_comments": "Comentarios"
        }),
        use_container_width=True,
        hide_index=True
    )

with tab3:
    pivot_df = pd.pivot_table(
        filtered_users,
        values=["total_posts", "total_comments"],
        index=["city", "company_name"],
        aggfunc="sum",
        fill_value=0
    ).reset_index()
    pivot_df.columns = ["Ciudad", "Empresa", "Total Publicaciones", "Total Comentarios"]
    st.dataframe(pivot_df, use_container_width=True, hide_index=True)

# Botones de descarga
st.markdown("### 📥 Exportar Reporte Filtrado")
dl_col1, dl_col2, _ = st.columns([1, 1, 2])

with dl_col1:
    csv_data = convert_df_to_csv(filtered_users)
    st.download_button(
        label="📄 Descargar Resumen (CSV)",
        data=csv_data,
        file_name="reporte_usuarios_jsonplaceholder.csv",
        mime="text/csv",
        use_container_width=True
    )

with dl_col2:
    excel_data = convert_dfs_to_excel(filtered_users, filtered_posts)
    st.download_button(
        label="📗 Descargar Reporte Completo (Excel)",
        data=excel_data,
        file_name="dashboard_jsonplaceholder_etl.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )