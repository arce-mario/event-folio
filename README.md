# EventFolio 📸

Sistema de subida de fotos para eventos con transferencia automática por FTP.

## Características

- **Subida de fotos** vía web desde móviles (QR → página de subida)
- **Validación robusta**: extensiones, tamaño, tipo MIME
- **Transferencia FTP** automática a servidor destino en VPN
- **Sistema de reintentos** para transferencias fallidas
- **Frontend responsive** optimizado para móviles
- **100% self-hosted** con Python

## Arquitectura

```
┌─────────────┐     HTTP      ┌─────────────────┐     FTP      ┌─────────────┐
│   Móvil     │ ──────────►   │    Backend      │ ──────────►  │  Servidor   │
│  (Browser)  │   /upload     │   (FastAPI)     │   Puerto 21  │    FTP      │
└─────────────┘               └─────────────────┘              └─────────────┘
                                     │
                                     ▼
                              /var/app/uploads/
                              (almacenamiento temporal)
```

## Requisitos

- Python 3.10+
- Servidor FTP accesible (en la misma red/VPN)

## Instalación

### 1. Clonar y configurar entorno

```bash
cd app
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
# Copiar plantilla
cp .env.example .env

# Editar con tus valores
nano .env  # o tu editor preferido
```

Variables importantes:
- `FTP_HOST`: IP del servidor FTP (ej: `10.0.0.2`)
- `FTP_USER` / `FTP_PASSWORD`: Credenciales FTP
- `UPLOAD_TOKEN`: Token de seguridad para subidas
- `LOCAL_UPLOAD_DIR`: Directorio temporal de subidas

### 3. Ejecutar servidor

```bash
# Desarrollo
python main.py

# Producción
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Uso

### URL de Subida (para QR)

```
http://TU_IP:8000/?token=TU_TOKEN&event_id=nombre-evento
```

Genera un QR con esta URL para que los invitados suban fotos.

### Ejemplos con curl

#### Health Check
```bash
curl http://localhost:8000/health
```

#### Subir una imagen
```bash
curl -X POST "http://localhost:8000/upload?token=dev_token_123" \
  -F "files=@foto.jpg" \
  -F "event_id=boda-2024"
```

#### Subir múltiples imágenes
```bash
curl -X POST "http://localhost:8000/upload?token=dev_token_123" \
  -F "files=@foto1.jpg" \
  -F "files=@foto2.png" \
  -F "files=@foto3.jpeg" \
  -F "event_id=cumple-maria"
```

#### Ver cola de transferencias
```bash
curl "http://localhost:8000/admin/queue?token=dev_token_123"
```

#### Reintentar transferencias fallidas
```bash
curl -X POST "http://localhost:8000/admin/retry?token=dev_token_123"
```

#### Probar conexión FTP
```bash
curl "http://localhost:8000/admin/ftp-test?token=dev_token_123"
```

## Endpoints API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/` | Página de subida (frontend) |
| GET | `/health` | Estado del sistema |
| POST | `/upload` | Subir imágenes |
| GET | `/admin/queue` | Ver cola de transferencias |
| POST | `/admin/retry` | Reintentar transferencias fallidas |
| GET | `/admin/ftp-test` | Probar conexión FTP |

## Estructura del Proyecto

```
app/
├── main.py              # Aplicación FastAPI principal
├── config.py            # Configuración desde .env
├── validators.py        # Validación de archivos
├── ftp_client.py        # Cliente FTP
├── tasks.py             # Sistema de cola y reintentos
├── templates/
│   └── upload.html      # Plantilla de subida
├── static/
│   ├── style.css        # Estilos
│   └── upload.js        # JavaScript del frontend
├── requirements.txt     # Dependencias Python
├── Dockerfile           # Contenedor Docker
├── .env.example         # Plantilla de configuración
└── README.md            # Este archivo
```

## Docker

### Construir imagen

```bash
docker build -t eventfolio .
```

### Ejecutar contenedor

```bash
docker run -d \
  --name eventfolio \
  -p 8000:8000 \
  -v $(pwd)/uploads:/var/app/uploads \
  -e FTP_HOST=10.0.0.2 \
  -e FTP_USER=eventuploader \
  -e FTP_PASSWORD=tu_password \
  -e UPLOAD_TOKEN=tu_token_seguro \
  eventfolio
```

### Docker Compose

```yaml
version: '3.8'
services:
  eventfolio:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./uploads:/var/app/uploads
    environment:
      - FTP_HOST=10.0.0.2
      - FTP_USER=eventuploader
      - FTP_PASSWORD=${FTP_PASSWORD}
      - UPLOAD_TOKEN=${UPLOAD_TOKEN}
    restart: unless-stopped
```

## Configuración del Servidor FTP

El servidor FTP destino debe:

1. Estar accesible desde el backend (misma red/VPN)
2. Tener un usuario con permisos de escritura
3. Tener el directorio destino creado

Ejemplo con vsftpd:

```bash
# En el servidor FTP
sudo apt install vsftpd
sudo useradd -m eventuploader
sudo passwd eventuploader
sudo mkdir -p /srv/event_photos/incoming
sudo chown eventuploader:eventuploader /srv/event_photos/incoming
```

## Seguridad

- **Token de autenticación**: Requerido en todas las peticiones
- **Validación de archivos**: Solo imágenes permitidas
- **Límites de tamaño**: Configurable por archivo y por petición
- **Sanitización**: Event IDs y nombres de archivo sanitizados
- **Red interna**: Diseñado para ejecutar en VPN/red privada

## Extensiones Futuras

- [ ] Autenticación OAuth/JWT
- [ ] Compresión de imágenes antes de FTP
- [ ] Notificaciones por webhook
- [ ] Panel de administración web
- [ ] Soporte para vídeos cortos
- [ ] Galería de previsualización
- [ ] Múltiples destinos FTP

## Licencia

MIT License
