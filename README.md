# VoIP Onboarding API

Backend API para simplificar el onboarding de usuarios a un servicio VoIP con FreePBX.

## Funcionalidades

- Registro de usuarios con email/password
- Autenticación JWT
- Creación automática de extensiones SIP en FreePBX
- Entrega de credenciales SIP para configurar softphones (Linphone, etc.)

## Requisitos

- Python 3.9+
- FreePBX con REST API habilitada

## Instalación

```bash
# Clonar repositorio
cd voip-onboarding-api

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# o: venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores
```

## Configuración

Editar `.env` con los valores de tu entorno:

| Variable | Descripción |
|----------|-------------|
| `JWT_SECRET_KEY` | Clave secreta para firmar tokens JWT |
| `FREEPBX_HOST` | URL de tu servidor FreePBX |
| `FREEPBX_API_TOKEN` | Token de API de FreePBX |
| `SIP_DOMAIN` | Dominio/IP del servidor SIP |

### Configuración de FreePBX REST API

1. En FreePBX, ir a **Admin > System Admin > HTTP Server**
2. Habilitar API REST
3. Crear token de API en **Admin > API > Token**
4. Copiar el token a tu archivo `.env`

## Ejecución

```bash
# Desarrollo
uvicorn app.main:app --reload --port 8000

# Producción
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Autenticación

#### POST /auth/register
Registra un nuevo usuario y crea extensión SIP.

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "usuario@ejemplo.com", "password": "secreto123"}'
```

Respuesta:
```json
{
  "id": 1,
  "email": "usuario@ejemplo.com",
  "sip_extension": "1000",
  "is_active": true,
  "created_at": "2025-01-15T10:30:00Z"
}
```

#### POST /auth/login
Autenticar y obtener JWT token.

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "usuario@ejemplo.com", "password": "secreto123"}'
```

Respuesta:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### Credenciales SIP

#### GET /sip/credentials
Obtener credenciales SIP (requiere autenticación).

```bash
curl http://localhost:8000/sip/credentials \
  -H "Authorization: Bearer <tu-token>"
```

Respuesta:
```json
{
  "username": "1000",
  "password": "aB3dEf6gH9jK",
  "domain": "pbx.tudominio.com",
  "port": 5060,
  "transport": "udp",
  "display_name": "usuario",
  "auth_username": "1000"
}
```

## Configuración Linphone SDK

Usar las credenciales del endpoint `/sip/credentials`:

```kotlin
// Android - Linphone SDK
val authInfo = Factory.instance().createAuthInfo(
    credentials.username,      // username
    credentials.auth_username, // userid
    credentials.password,      // password
    null,                      // ha1
    null,                      // realm
    credentials.domain         // domain
)

val accountParams = core.createAccountParams()
val identity = Factory.instance().createAddress(
    "sip:${credentials.username}@${credentials.domain}"
)
accountParams.identityAddress = identity

val serverAddress = Factory.instance().createAddress(
    "sip:${credentials.domain}:${credentials.port};transport=${credentials.transport}"
)
accountParams.serverAddress = serverAddress
```

## Estructura del Proyecto

```
voip-onboarding-api/
├── app/
│   ├── main.py           # FastAPI app entry point
│   ├── config.py         # Settings from environment
│   ├── database.py       # SQLAlchemy setup
│   ├── dependencies.py   # FastAPI dependencies (auth)
│   ├── models/
│   │   └── user.py       # SQLAlchemy User model
│   ├── schemas/
│   │   └── user.py       # Pydantic schemas
│   ├── routers/
│   │   ├── auth.py       # /auth endpoints
│   │   └── sip.py        # /sip endpoints
│   └── services/
│       ├── auth.py       # Auth/JWT logic
│       └── freepbx.py    # FreePBX API client
├── .env.example
├── requirements.txt
└── README.md
```

## Documentación API

Con el servidor corriendo, visita:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
