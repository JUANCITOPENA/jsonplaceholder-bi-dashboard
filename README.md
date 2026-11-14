<<<<<<< HEAD
# 📊 Dashboard Analítico ETL | JSONPlaceholder API

Aplicación web interactiva desarrollada con **Python**, **Streamlit**, **Pandas** y **Plotly** que ejecuta un flujo ETL completo sobre las APIs públicas de JSONPlaceholder (`users`, `posts`, `comments`).

## 🚀 Características Principales
- **Pipeline ETL Automatizado:** Extracción HTTP con manejo de errores, normalización de objetos JSON anidados (`address`, `company`) y cruce relacional mediante `userId` y `postId`.
- **Optimización:** Caché de consultas mediante `@st.cache_data` (TTL de 1 hora) para minimizar latencia y llamadas redundantes.
- **KPIs Ejecutivos:** Total de usuarios, publicaciones, comentarios y tasa promedio de comentarios por publicación.
- **Filtros Dinámicos:** Segmentación encadenada por Ciudad, Empresa, Usuario y rango de publicaciones.
- **Visualización Interactiva:** Gráficos de barras agrupadas, anillo/pastel, dispersión multivariable y tabla dinámica.
- **Exportación:** Descarga instantánea en formatos `.csv` y `.xlsx` multi-hoja.

## 🛠️ Instalación y Ejecución Local

1. Clonar el repositorio:
   ```bash
   git clone [https://github.com/TU_USUARIO/jsonplaceholder-bi-dashboard.git](https://github.com/TU_USUARIO/jsonplaceholder-bi-dashboard.git)
   cd jsonplaceholder-bi-dashboard
=======

>>>>>>> fc3f070b4ec55e20f41f9a808acccde703ec9545
