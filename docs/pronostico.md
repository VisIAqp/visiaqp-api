# Despliegue de VisIAqp con Docker Compose

Ejecuta los comandos desde la raíz de VisIAqp, donde están `docker-compose.yml`, `db/`, `visiaqp-api/` y `visiaqp-client/`.

## Configuración inicial

1. En el `.env` de la raíz, define `DB_ROOT_PASSWORD` con la contraseña de MySQL. Si reutilizas un volumen, usa la contraseña con la que ya está inicializado. Opcionalmente define `VISIAQP_PORT` si quieres cambiar el puerto web local de 8080.
2. En `visiaqp-api/.env`, configura `DATABASE_URL`, `SECRET_KEY` y `MOTOR_API_KEY`. Puedes partir de `visiaqp-api/.env.template`. Compose sustituye el host y el puerto del DSN por `db:3306` y usa el usuario, contraseña y base del DSN. En la nube, usa una cuenta de MySQL con los permisos necesarios sobre `visiaqp`, incluido el permiso para aplicar las migraciones. En una instalación nueva con el Compose actual puedes usar la cuenta root para la configuración inicial.
3. Si ya tienes MySQL en Docker, comprueba qué volumen usa antes de levantar el conjunto. El nombre de proyecto predeterminado del Compose de la raíz es `visiaqp`. Si tu volumen pertenece al proyecto anterior `visiaqp-api`, ejecuta los comandos con `docker compose -p visiaqp-api` para reutilizarlo. Haz una copia de seguridad antes de aplicar las migraciones sobre una base existente.
4. Si instalaste las unidades anteriores en un servidor, desactiva el generador y el temporizador antes de arrancar sus equivalentes en Docker.

```bash
docker inspect visiaqp-db --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Name}}{{end}}{{end}}'
```

## Arranque y verificación

```bash
docker compose up -d --build
docker compose ps -a
docker compose logs migraciones
docker compose logs -f pronostico entrenamiento
```

MySQL aplica `db/init/01_schema.sql` cuando inicializa un volumen vacío. El contenedor `migraciones` aplica Alembic antes del arranque del API y los procesos de pronóstico. Su estado esperado al finalizar es `Exited (0)`.

Abre [VisIAqp](http://localhost:8080), inicia sesión y entra en Monitoreo. Si aún no hay una cuenta de administrador, créala con `docker compose exec api python -m scripts.crear_admin`. Nginx sirve Angular y envía las solicitudes de `/api/` al backend. Puedes comprobar el arranque del API desde el navegador en [localhost:8080/health](http://localhost:8080/health).

En la nube, publica el frontend y el API bajo el mismo dominio mediante un proxy HTTPS del servidor que reenvíe a `http://127.0.0.1:8080` y preserve `Host` y `X-Forwarded-Proto`. Configura `API_BASE_URL` del motor local con el origen HTTPS de ese dominio, sin el sufijo `/api`, y usa el mismo `MOTOR_API_KEY` del backend. Los puertos de MySQL están enlazados a la interfaz local. Para levantar MySQL de pruebas, usa `docker compose up -d db_test`.

## Pronóstico automático

- **Generación.** El contenedor `pronostico` comprueba cada minuto si puede emitir un pronóstico nuevo para las cámaras con un modelo vigente.
- **Entrenamiento.** El contenedor `entrenamiento` revisa las cámaras fijas, activas y con polígono al arrancar y luego cada día a las 03:00, hora de Lima. Entrena cuando hay suficiente historial con firma de captura y reentrena cuando el último bloque válido ha avanzado al menos siete días desde el corte del modelo vigente. Si cambia la configuración de captura, ajusta un modelo para la firma nueva cuando hay datos suficientes.

La primera publicación depende de que la cámara cumpla los mínimos de historial y tenga tres bloques recientes con cobertura suficiente. Hasta entonces, Monitoreo indica el estado de disponibilidad.
