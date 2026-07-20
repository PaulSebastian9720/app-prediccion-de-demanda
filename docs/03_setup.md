# Guía de Arranque e Instalación

Esta guía detalla los pasos para instalar, configurar y desplegar el entorno completo de desarrollo.

## 1. Clonación del Repositorio y Documentación Interna
Para clonar este repositorio e ingresar a la carpeta del proyecto:
```bash
git clone https://github.com/PaulSebastian9720/app-prediccion-de-demanda.git
cd app-prediccion-de-demanda
```
*   **Documentación Backend:** Consulta detalles adicionales en [app-backend/README.md](file:///home/paul/universidad/septimo_v2/Aprendiza_Automatico/app-prediccion-de-demanda/app-backend/README.md).
*   **Documentación Frontend:** Consulta detalles adicionales en [app-fronted/README.md](file:///home/paul/universidad/septimo_v2/Aprendiza_Automatico/app-prediccion-de-demanda/app-fronted/README.md).

## 2. Requisitos Previos e Instalación

*   **Python & uv:** Instala `uv` con:
    - *Linux/macOS:* `curl -LsSf https://astral.sh/uv/install.sh | sh`
    - *Windows:* `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
*   **Node.js & npm (v18+):** En Linux/macOS usa `nvm`:
    `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash`
    Luego activa e instala: `nvm install --lts && nvm use --lts`.
*   **Docker:** Instala Docker Engine/Desktop para correr la base de datos PostgreSQL 17.

## 3. Stack de Dependencias y Versiones Clave

### Backend Core & Base de Datos
| Tecnología / Badge | Versión | Descripción |
| :--- | :--- | :--- |
| ![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white) | `>= 3.12` | Entorno de ejecución asíncrono de alto rendimiento. |
| ![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi) | `>= 0.115.0` | Framework web asíncrono interactivo para la exposición de la API. |
| SQLAlchemy | `>= 2.0.36` | ORM para la interacción asíncrona con la base de datos PostgreSQL. |
| Asyncpg | `>= 0.30.0` | Driver asíncrono nativo para conexiones con la base de datos. |
| Alembic | `>= 1.14.0` | Gestor de migraciones incrementales del esquema relacional. |

### Machine Learning, Ingesta y LLM
| Tecnología / Badge | Versión | Descripción |
| :--- | :--- | :--- |
| ![XGBoost](https://img.shields.io/badge/XGBoost-14B8A6?style=flat) | `>= 2.1.2` | Algoritmo de Gradient Boosting para la predicción de demanda. |
| ![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-F97316?style=flat&logo=scikitlearn) | `== 1.8.*` | Módulo para preprocesamiento y escalado de features. |
| WeasyPrint | `>= 63.0` | Generador de reportes PDF ejecutivos renderizados desde HTML/CSS. |
| ![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat&logo=openai) | `>= 1.54.0` | Integración con `gpt-4o-mini` para explicaciones en lenguaje natural. |

### Frontend & Framework UI
| Tecnología / Badge | Versión | Descripción |
| :--- | :--- | :--- |
| ![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat&logo=nextdotjs) | `16.2.10` | Framework web de producción estructurado en React. |
| ![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB) | `19.2.4` | Biblioteca nativa para diseño de interfaces de usuario. |
| ![TailwindCSS](https://img.shields.io/badge/TailwindCSS-38B2AC?style=flat&logo=tailwindcss) | `v4` | Framework CSS basado en utilidades de última generación. |
| Sonner | `^2.0.7` | Notificaciones toast flotantes con micro-animaciones en UI. |

## 4. Configuración de Git (Paul Developer)
```bash
git config --global user.name "Paul"
git config --global user.email "paul@example.com"
```

## 5. Configuración de Variables de Entorno (.env)
*   **Backend (`app-backend/.env`):** Copia desde la plantilla: `cp .env.example .env`. Edita los valores de `DATABASE_URL` (para apuntar a `localhost:5434`), `JWT_SECRET_KEY` para tokens de seguridad y la opcional `OPENAI_API_KEY` para explicaciones con LLM.
*   **Frontend (`app-fronted/.env.local`):** Copia la plantilla: `cp .env.example .env.local`. Configura la variable `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` para apuntar al backend.

## 6. Despliegue del Sistema y Mapeo de Puertos
El sistema expone los siguientes puertos por defecto:
*   **Base de Datos (Postgres 17):** Puerto host **`5434`** (mapeado a `5432` en el contenedor).
*   **Backend API (FastAPI):** Puerto host **`8000`** (`http://localhost:8000`).
*   **Frontend (Next.js):** Puerto host **`3000`** (`http://localhost:3000`).

### Despliegue Paso a Paso
1.  **Base de Datos:** Levanta el contenedor en la carpeta `app-backend`:
    ```bash
    make db-up
    ```
2.  **Backend:** Instala dependencias con `uv`, corre las migraciones, las semillas e inicia desarrollo:
    ```bash
    make install
    make migrate
    make seed
    make seed-catalog
    make create-admin
    make dev
    ```
3.  **Frontend:** Instala e inicia el servidor en la carpeta `app-fronted`:
    ```bash
    npm install
    npm run dev
    ```

## 7. Troubleshooting
*   **Puerto 5434 ocupado:** Detén servicios PostgreSQL en tu sistema local (`sudo systemctl stop postgresql`) o edita el puerto en `docker/compose.yml`.
*   **WeasyPrint (Error de dependencias PDF):** Instala las librerías nativas:
    - *Debian/Ubuntu:* `sudo apt install shared-mime-info libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0`
    - *macOS:* `brew install cairo pango gdk-pixbuf libffi`
*   **Error `401 Unauthorized` persistente:** Borra LocalStorage en el navegador e ingresa con las credenciales de administrador.
