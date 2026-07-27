# Aplicación de Predicción de Demanda para Veterinarias

Sistema que predice la demanda de venta por categoría de producto en una
veterinaria (día, semana o mes) y explica el porqué de cada predicción, para
apoyar decisiones de reposición de inventario.

[![Ver video](https://img.youtube.com/vi/FdomcplaQsI/maxresdefault.jpg)](https://www.youtube.com/watch?v=FdomcplaQsI)

## Problema

Hoy la reposición de stock en una veterinaria se decide "a ojo", sin un
histórico analizado. Esto genera quiebres de stock en temporada alta o
capital inmovilizado en exceso de inventario. Además, el dato crudo con el
que se parte (ventas diarias por categoría) no es utilizable por un modelo
tal cual llega: tiene huecos de fechas, valores inconsistentes y ninguna
señal de tendencia o estacionalidad todavía construida.

## Solución

Una aplicación web que:

- Ingiere el historial real de ventas (carga manual o por archivo CSV/XLSX).
- Transforma ese historial en variables predictivas (lags, medias móviles,
  variables de calendario, codificación de categoría).
- Entrena y versiona un modelo XGBoost, activando automáticamente la versión
  con mejor error de prueba (MAE).
- Predice la demanda por categoría y **explica** cada predicción (rango de
  confianza, comparación con el stock actual y con el mismo día de la semana
  anterior).
- Genera reportes en PDF y gestiona alertas de stock crítico.

## Arquitectura

```mermaid
graph TD
    subgraph Frontend [Next.js App]
        UI[UI / Dashboard] -->|apiJson / apiBlob| Client[HTTP Client / Auth Interceptor]
    end
    subgraph Backend [FastAPI API]
        Client -->|REST API over HTTP/S| Routes[Routers /api/v1]
        Routes -->|Inferencia| MLReg[MLModelRegistry]
        MLReg -->|Carga Modelos| XGB[XGBoost Models /artifacts]
        Routes -->|Async Query| DB[(PostgreSQL 17)]
        Routes -->|Explicación de Predicción| OpenAI[OpenAI API / gpt-4o-mini]
    end
```

Detalle completo en [`docs/01_architecture.md`](docs/01_architecture.md).

## Tecnologías

![Next.js](https://img.shields.io/badge/Next.js_16-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React_19-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwindcss&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-1560bd?style=for-the-badge)
![Alembic](https://img.shields.io/badge/Alembic-6BA81E?style=for-the-badge)
![WeasyPrint](https://img.shields.io/badge/WeasyPrint_(PDF)-9c27b0?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

## Estructura del proyecto

```
app-backend/src/app/    # API FastAPI
├── api/                # Routers /api/v1
├── ml/                 # Registro y entrenamiento del modelo
├── services/           # Lógica de negocio
├── db/                 # Modelos SQLAlchemy
└── schemas/            # Esquemas Pydantic

app-fronted/            # Next.js App Router
├── app/(dashboard)/    # Páginas del panel
├── components/         # Componentes de UI
└── lib/                # Clientes de API
```

## Colaboradores

- **Paul Sebastián** — pnaspudv@est.ups.edu.ec — [@PaulSebastian9720](https://github.com/PaulSebastian9720)
- **Jennyfer Ramírez** — jramirezs11@est.ups.edu.ec — [@jennyfer04ramirez](https://github.com/jennyfer04ramirez)
- **Juan Fernando** — jfernandoalz18@gmail.com — [@Juanfernando518](https://github.com/Juanfernando518)
- **Johnny** — 0996140701lol@gmail.com — [@johnny567w](https://github.com/johnny567w)

## Documentación adicional

¿Quieres conocer más sobre este proyecto? Revisa [`docs/`](docs/) — arquitectura,
glosario, setup y referencia de API. También hay un README propio con la
estructura específica de cada proyecto en [`app-backend/`](app-backend/README.md)
y en [`app-fronted/`](app-fronted/README.md).
