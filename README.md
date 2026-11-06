# Transportes Yuyari

Sistema web para la operación de una empresa de turismo y transporte en Arequipa: landing pública y panel privado de gestión.

## Funciones

- Landing adaptable con portada, experiencias, sección Nosotros, contacto y contenido configurable desde el panel.
- Operaciones para servicios turísticos, traslados, taxis, transporte de personal y logística.
- Gestión de reservas, rutas, paradas, unidades, capacidad de asientos y disponibilidad por mantenimiento.
- Manifiesto de pasajeros por servicio con documento, edad, asiento e información de acompañamiento de menores; impresión o guardado como PDF.
- Checklist preoperacional, incidencias, datos del conductor y número de licencia.
- Clientes con persona de contacto, teléfono adicional, WhatsApp y redes sociales.
- Gastos y compras clasificables como costos fijos o variables, además de reportes y exportación.
- Inicio de sesión JWT y permisos por usuario/módulo en el panel.
- Backend Django REST Framework. SQLite se usa por defecto en desarrollo; PostgreSQL se configura para producción.

## Requisitos locales

- Node.js 20.19+ o 22.12+.
- pnpm.
- Python 3.11+.

## Iniciar en Windows

Desde la carpeta raíz del proyecto, instala las dependencias del frontend:

```powershell
pnpm install
Copy-Item .env.example .env
```

En una primera ejecución, prepara el backend en otra terminal:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py bootstrap_admin
python manage.py runserver
```

En la terminal de la raíz del proyecto:

```powershell
pnpm dev
```

También puedes iniciar ambos servicios con doble clic en `Iniciar Yuyari.bat` después de instalar los requisitos. Mantén abiertas las ventanas de terminal mientras uses el sistema.

En desarrollo, `bootstrap_admin` crea el usuario local `admin` con contraseña `admin123`. Cámbiala antes de usar datos reales. Para cuentas del equipo, inicia sesión y entra a **Usuarios**.

La API local queda en `http://127.0.0.1:8000/api/` y Vite en `http://localhost:5173`. El archivo `.env` de la raíz define `VITE_API_URL`; `.env` y la base de datos local no se publican en Git.

## Configuración de producción

No guardes claves ni contraseñas en el repositorio. Configura las variables de entorno en el proveedor de despliegue:

- `DJANGO_SECRET_KEY`: clave aleatoria larga y privada.
- `DJANGO_ADMIN_PASSWORD`: contraseña segura para crear o restablecer el administrador inicial.
- `DEBUG=false`.
- `DATABASE_URL`: conexión a PostgreSQL.
- `ALLOWED_HOSTS`: dominios del backend.
- `CORS_ALLOWED_ORIGINS`: dominios de la landing y el frontend.
- `VITE_API_URL`: URL pública del backend para compilar el frontend.

Para Railway, configura el comando de inicio del backend para aplicar migraciones antes de levantar Gunicorn, por ejemplo `python manage.py migrate && gunicorn config.wsgi:application`. En un despliegue nuevo, establece `DJANGO_ADMIN_PASSWORD` al ejecutar `python manage.py bootstrap_admin`. La contraseña local `admin123` no se acepta para crear o restablecer la cuenta si `DEBUG=false`.

El manifiesto PDF y el checklist son documentos internos generados para imprimir y firmar. No sustituyen la presentación electrónica oficial que pudiera corresponder ante SUTRAN.
