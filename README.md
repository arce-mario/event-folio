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
- `DELETE_AFTER_FTP`: Eliminar archivos locales tras transferencia FTP exitosa (`true`/`false`, default: `true`)

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

Hay dos formas de ejecutar EventFolio en Docker, dependiendo de tu configuración de red.

### Opción A: Ejecución estándar (FTP accesible directamente)

Usa esta opción si el servidor FTP es accesible desde el host sin VPN.

```bash
# Construir imagen con UID/GID del usuario actual
docker build \
  --build-arg APP_UID=$(id -u) \
  --build-arg APP_GID=$(id -g) \
  -t eventfolio .

# Ejecutar contenedor
docker run -d \
  --name eventfolio \
  -p 8000:8000 \
  -v $(pwd)/uploads:/var/app/uploads \
  --user $(id -u):$(id -g) \
  -e FTP_HOST=10.0.0.2 \
  -e FTP_USER=eventuploader \
  -e FTP_PASSWORD=tu_password \
  -e UPLOAD_TOKEN=tu_token_seguro \
  eventfolio
```

### Opción B: Ejecución con OpenVPN (FTP en red VPN)

Usa esta opción si el servidor FTP está en una red VPN y OpenVPN corre en Docker.

```bash
# Construir imagen (sin build args, corre como root)
docker build -t eventfolio .

# 1. Crear directorio uploads con permisos amplios
mkdir -p uploads
sudo chown -R 0:0 uploads
sudo chmod -R 777 uploads

# 2. Iniciar OpenVPN con puerto expuesto para EventFolio
docker run -d \
  --name openvpn \
  --cap-add=NET_ADMIN \
  --device=/dev/net/tun \
  -p 1194:1194/udp \
  -p 5110:8000 \
  -v /ruta/a/openvpn-data:/etc/openvpn \
  kylemanna/openvpn

# 3. Iniciar EventFolio usando la red del contenedor OpenVPN
docker run -d \
  --name eventfolio \
  --network container:openvpn \
  -v $(pwd)/uploads:/var/app/uploads \
  -e FTP_HOST=192.168.255.6 \
  -e FTP_USER=eventuploader \
  -e FTP_PASSWORD=tu_password \
  -e UPLOAD_TOKEN=tu_token_seguro \
  -e DELETE_AFTER_FTP=true \
  -e PORT=8000 \
  eventfolio
```

**Nota**: Con `--network container:openvpn`, EventFolio comparte la red del contenedor OpenVPN y puede acceder a clientes VPN. El puerto se expone en OpenVPN (`-p 5110:8000`), no en EventFolio.

### Docker Compose

```yaml
version: '3.8'
services:
  eventfolio:
    build:
      context: .
      args:
        APP_UID: ${APP_UID:-1000}
        APP_GID: ${APP_GID:-1000}
    ports:
      - "8000:8000"
    volumes:
      - ./uploads:/var/app/uploads
    user: "${APP_UID:-1000}:${APP_GID:-1000}"
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

### Linux (vsftpd)

```bash
# En el servidor FTP
sudo apt install vsftpd
sudo useradd -m eventuploader
sudo passwd eventuploader
sudo mkdir -p /srv/event_photos/incoming
sudo chown eventuploader:eventuploader /srv/event_photos/incoming
```

### Windows (IIS FTP)

Ejecuta todos los comandos en **PowerShell como Administrador**.

#### Paso 1: Habilitar características de Windows

```powershell
# Habilitar IIS y FTP Server
Enable-WindowsOptionalFeature -Online -FeatureName "IIS-WebServerRole" -NoRestart
Enable-WindowsOptionalFeature -Online -FeatureName "IIS-ManagementConsole" -All -NoRestart
Enable-WindowsOptionalFeature -Online -FeatureName "IIS-FTPServer" -NoRestart
Enable-WindowsOptionalFeature -Online -FeatureName "IIS-FTPSvc" -NoRestart

# Reiniciar si es necesario
Restart-Computer -Force
```

#### Paso 2: Crear usuario y directorio

```powershell
# Crear usuario local (cambia la contraseña)
$pass = ConvertTo-SecureString "TuPasswordSegura123" -AsPlainText -Force
New-LocalUser -Name "eventuploader" -Password $pass -FullName "Event Uploader" -PasswordNeverExpires

# Agregar al grupo Users
Add-LocalGroupMember -Group "Users" -Member "eventuploader"

# Crear directorio para fotos
$path = "C:\srv\event_photos\incoming"
New-Item -ItemType Directory -Path $path -Force

# Asignar permisos completos al usuario
icacls $path /grant "eventuploader:(OI)(CI)F" /T
```

#### Paso 3: Configurar sitio FTP en IIS

```powershell
Import-Module WebAdministration

# Eliminar sitio FTP existente (si existe)
Remove-WebSite -Name "EventPhotosFTP" -ErrorAction SilentlyContinue

# Crear nuevo sitio FTP
New-WebFtpSite -Name "EventPhotosFTP" -Port 21 -PhysicalPath $path

# Habilitar autenticación básica
Set-ItemProperty "IIS:\Sites\EventPhotosFTP" -Name ftpServer.security.authentication.basicAuthentication.enabled -Value $true

# Configurar autorización (permissions=3 = Read+Write)
Add-WebConfiguration "/system.ftpServer/security/authorization" -Value @{accessType="Allow"; users="eventuploader"; permissions=3} -PSPath IIS:\ -Location "EventPhotosFTP"

# Deshabilitar SSL (para redes privadas/VPN)
Set-ItemProperty "IIS:\Sites\EventPhotosFTP" -Name ftpServer.security.ssl.controlChannelPolicy -Value 0
Set-ItemProperty "IIS:\Sites\EventPhotosFTP" -Name ftpServer.security.ssl.dataChannelPolicy -Value 0

# Reiniciar servicio FTP
Restart-Service ftpsvc
```

#### Paso 4: Configurar modo pasivo FTP

El modo pasivo es necesario para transferencias a través de VPN/NAT:

```powershell
# Configurar rango de puertos pasivos (50000-50100)
Set-WebConfigurationProperty -pspath 'MACHINE/WEBROOT/APPHOST' -filter "system.ftpServer/firewallSupport" -name "lowDataChannelPort" -value 50000
Set-WebConfigurationProperty -pspath 'MACHINE/WEBROOT/APPHOST' -filter "system.ftpServer/firewallSupport" -name "highDataChannelPort" -value 50100

# Configurar IP externa del servidor FTP (usa tu IP de VPN)
Set-ItemProperty "IIS:\Sites\EventPhotosFTP" -Name ftpServer.firewallSupport.externalIp4Address -Value "192.168.255.6"

# Reiniciar servicio FTP
Restart-Service ftpsvc
```

#### Paso 5: Configurar Firewall

```powershell
# Permitir FTP puerto 21
New-NetFirewallRule -DisplayName "FTP Server Port 21" -Direction Inbound -Protocol TCP -LocalPort 21 -Action Allow

# Permitir puertos pasivos FTP
New-NetFirewallRule -DisplayName "FTP Passive Ports" -Direction Inbound -Protocol TCP -LocalPort 50000-50100 -Action Allow

# Permitir FTP desde subred VPN (ajusta la IP según tu red)
New-NetFirewallRule -DisplayName "FTP from VPN" -Direction Inbound -Protocol TCP -LocalPort 21 -RemoteAddress 192.168.255.0/24 -Action Allow

# Permitir ping desde VPN (opcional, para diagnóstico)
New-NetFirewallRule -DisplayName "ICMP from VPN" -Direction Inbound -Protocol ICMPv4 -RemoteAddress 192.168.255.0/24 -Action Allow
```

#### Paso 6: Verificar configuración

```powershell
# Probar login FTP local
ftp localhost
# Usuario: eventuploader
# Contraseña: TuPasswordSegura123

# Verificar servicio FTP activo
Get-Service ftpsvc

# Ver sitios FTP configurados
Get-WebSite | Where-Object { $_.Bindings -match "ftp" }
```

#### Solución de problemas

Si el login falla con "530 User cannot log in":

```powershell
# Restablecer contraseña del usuario
$pass = ConvertTo-SecureString "TuPasswordSegura123" -AsPlainText -Force
Set-LocalUser -Name "eventuploader" -Password $pass

# Verificar que el usuario existe
Get-LocalUser -Name "eventuploader"

# Reiniciar servicio FTP
Restart-Service ftpsvc
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
