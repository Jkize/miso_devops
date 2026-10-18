# API de lista negra global

Microservicio Flask para agregar y consultar correos bloqueados. Persistencia en
PostgreSQL y autenticación Bearer con JWT predefinido. El despliegue es manual.

## Ejecución local en Windows / PowerShell

Requisitos: Python 3.10 o superior y Docker Desktop con motor Linux activo.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Editar `.env`: cambiar `POSTGRES_PASSWORD`, actualizar la misma contraseña en
`DATABASE_URL` y configurar `JWT_SECRET_KEY` con un secreto aleatorio de al menos
32 bytes. Si la contraseña tiene caracteres reservados de una URL, codificarlos
en `DATABASE_URL`. `.env` no se versiona. No sobrescribir un `.env` ya configurado.

```powershell
docker compose up -d --wait
.\.venv\Scripts\python.exe -m flask --app application db upgrade
.\.venv\Scripts\python.exe -m flask --app application run --host 127.0.0.1 --port 5000
```

En otra terminal, generar el token para Postman:

```powershell
.\.venv\Scripts\python.exe -m flask --app application issue-token
```

El token dura siete días y se reutiliza en ambas operaciones. Copiarlo únicamente
al valor local de `token` en Postman. No incluirlo en exports, capturas ni commits.
Rotar el secreto invalida los tokens existentes. No hay endpoint de login.

Para detener PostgreSQL conservando sus datos: `docker compose stop`.
El volumen `postgres_data` permite conservarlos al recrear el contenedor.

## Contrato HTTP

Las operaciones de negocio requieren `Authorization: Bearer <token>`.

### POST /blacklists

```json
{
  "email": "customer@example.com",
  "app_uuid": "94b8097c-e7ab-4e50-9035-eabda6514e81",
  "blocked_reason": "Solicitud del cliente"
}
```

- `email`: obligatorio, formato válido y máximo 254 caracteres. Se eliminan
  espacios exteriores y se guarda en minúsculas como política de este servicio.
- `app_uuid`: obligatorio, UUID válido.
- `blocked_reason`: opcional o `null`, máximo 255 caracteres.
- Campos desconocidos se rechazan. IP y fecha UTC se asignan en el servidor.

Respuesta 201:

```json
{"message": "Correo agregado a la lista negra."}
```

Respuestas de error: 400 para entrada inválida, 401 para autenticación ausente,
inválida o expirada, 409 para correo ya registrado y 503 para fallo de base de datos.
Los duplicados no modifican el motivo ni los datos de auditoría originales.

### GET /blacklists/<email>

Codificar el correo al construir la URL (por ejemplo `+` como `%2B`). Respuesta 200:

```json
{"blacklisted": true, "blocked_reason": "Solicitud del cliente"}
```

Si no existe: `{"blacklisted": false, "blocked_reason": null}` con HTTP 200.
Correo inválido: 400. Token ausente, inválido o expirado: 401.

### GET /health

Sin autenticación. Verifica conectividad con PostgreSQL mediante `SELECT 1`.
Retorna 200 con `status` y `version`, o 503 si falla la conexión. No garantiza
que las migraciones estén aplicadas: verificarlas antes de abrir tráfico.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas automáticas usan SQLite en memoria para aislar escenarios HTTP.
La migración, los tipos PostgreSQL y la persistencia requieren verificación adicional
contra PostgreSQL real; SQLite no reemplaza esa verificación.

Con PostgreSQL local activo y migrado, ejecutar también:

```powershell
$env:TEST_POSTGRES="1"
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:TEST_POSTGRES
```

La prueba de integración crea un correo único, reinicia la instancia de aplicación,
comprueba persistencia, UUID y fecha con zona horaria; al terminar borra solo ese
registro de prueba. PostgreSQL se expone localmente en el puerto `55432` para
evitar conflictos con instalaciones existentes en `5432`.

Importar los JSON de `postman/`, seleccionar el environment local y asignar `token`.
Ejecutar la colección en orden con Collection Runner. Se generan correos nuevos por
corrida para poder repetirla. La colección contiene aserciones y ejemplos.
Publicar su documentación desde Postman y añadir la URL al informe de entrega.

## Estructura

- `application.py`: punto de entrada WSGI para Beanstalk.
- `blacklist_service/`: fábrica de aplicación, extensiones, modelos, validación y recursos.
- `migrations/`: esquema versionado; aplicar con `flask db upgrade`.
- `tests/`: escenarios HTTP, autenticación, límites y datos de auditoría.
- `postman/`: colección y environment sin secretos.
- `compose.yaml`: PostgreSQL local, accesible solo desde loopback.

## Preparación para Elastic Beanstalk

`Procfile` inicia Gunicorn en Linux. Usar una plataforma Python compatible con las
dependencias fijadas. Configurar `DATABASE_URL` y `JWT_SECRET_KEY`
en el entorno antes de cargar el ZIP. `.ebextensions/01_migrations.config`
ejecuta `flask db upgrade` en una sola instancia durante cada despliegue manual;
si el esquema ya está actualizado, no aplica cambios. Un fallo de migración
detiene el despliegue. No ejecutar despliegues concurrentes contra la misma base.

`TRUSTED_PROXY_HOPS` es 0 localmente: cabeceras `X-Forwarded-For` no se aceptan.
En AWS, verificar la cadena real balanceador/proxy y restringir el acceso directo
a instancias antes de ajustar ese valor. Un valor incorrecto permite falsificar IP.

Preparar un ZIP de código con `application.py`, `requirements.txt`, `Procfile`,
`blacklist_service/`, `migrations/` y `.ebextensions/` en la raíz. Excluir material del curso,
credenciales, entorno virtual, cachés y `.git`. Un ZIP manual no respeta
automáticamente `.gitignore`. `.ebextensions/02_healthcheck.config` configura
`/health` como ruta de health check con respuesta esperada HTTP 200.
La API ya fue verificada en AWS. La versión del experimento se define en
`application.py` y se muestra en `/health`: `exp03-additional-batch`.
La publicación de Postman y los cuatro experimentos de despliegue siguen pendientes.
