# Guía de Docker y Contenedores

Este documento detalla la configuración y comandos necesarios para desplegar el sistema completo utilizando contenedores Docker.

---

## 1. Arquitectura de Contenedores y Mapeo de Puertos
El sistema completo puede levantarse en red aislada utilizando Docker Compose:
*   **Contenedor `ventas-forecast-db`:** Corre PostgreSQL 17 Alpine. Puerto interno `5432` expuesto al puerto host **`5434`** para evitar colisiones con otros Postgres locales.
*   **Contenedor `ventas-forecast-backend`:** Compila el backend FastAPI usando el `Dockerfile` optimizado. Puerto host **`8000`**.
*   **Red de Comunicación:** Se define una red tipo bridge llamada `ventas-forecast-network` para comunicación DNS interna.
*   **Volumen de Persistencia:** Se crea un volumen persistente llamado `ventas_forecast_pgdata` mapeado a `/var/lib/postgresql/data`.

---

## 2. Archivos de Configuración Docker

### A. Dockerfile del Backend (`app-backend/Dockerfile`)
Utiliza una compilación multietapa (*multi-stage build*) para optimizar el peso final de la imagen, copiando el entorno generado de `uv` y configurando las librerías compartidas necesarias de WeasyPrint.

### B. Compose de Desarrollo (`docker/compose.yml`)
Levanta **únicamente** el contenedor de base de datos PostgreSQL 17 en el puerto `5434`. Útil cuando quieres correr el backend localmente en tu host para depurar código rápido.

### C. Compose de Producción/Integración (`app-backend/docker-compose.yml`)
Orquesta ambos contenedores (`db` y `backend`) juntos. Incluye un *Healthcheck* para garantizar que el backend no inicie hasta que la base de datos esté lista y saludable (`service_healthy`).

---

## 3. Comandos de Operación con Docker

Desplázate a la carpeta `app-backend` y utiliza los comandos del `Makefile` o comandos nativos:

### A. Construir y levantar todo el stack (DB + Backend)
```bash
# Opción usando Makefile:
make docker-up

# Comando nativo equivalente:
docker compose up -d --build
```

### B. Detener y remover contenedores
```bash
# Opción usando Makefile:
make docker-down

# Comando nativo equivalente:
docker compose down
```

### C. Monitorear logs del backend en tiempo real
```bash
# Opción usando Makefile:
make docker-logs

# Comando nativo equivalente:
docker compose logs -f backend
```

### D. Reconstruir imágenes limpiando caché
```bash
docker compose build --no-cache
```

---

## 4. Solución de Problemas de Docker (Troubleshooting)

*   **Error: `database system is shutting down` o corrupción de volumen:**
    Si los datos históricos de volumen quedan corruptos en pruebas locales, limpia el volumen persistente (¡Atención: esto borra todas tus ventas e histórico!):
    ```bash
    docker compose down -v
    ```
*   **Error de Healthcheck en backend (`service unhealthy`):**
    El healthcheck ejecuta `curl -f http://localhost:8000/api/v1/health`. Si falla, revisa con `docker logs ventas-forecast-backend` para verificar si las variables de entorno relativas a `DATABASE_URL` son correctas.

---

## 5. Documentación Adicional
Para configuraciones de desarrollo local no basadas puramente en contenedores, por favor revisa [03_setup.md](file:///home/paul/universidad/septimo_v2/Aprendiza_Automatico/app-prediccion-de-demanda/docs/03_setup.md), así como los READMEs de cada módulo:
*   **README Backend:** [app-backend/README.md](file:///home/paul/universidad/septimo_v2/Aprendiza_Automatico/app-prediccion-de-demanda/app-backend/README.md)
*   **README Frontend:** [app-fronted/README.md](file:///home/paul/universidad/septimo_v2/Aprendiza_Automatico/app-prediccion-de-demanda/app-fronted/README.md)
