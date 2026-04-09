# ScrappyDoo — Descarga de Datos Hidrometeorológicos del SENAMHI

Herramienta de scraping para descargar datos hidrometeorológicos de estaciones registradas en el [SENAMHI](https://www.senamhi.gob.pe), con interfaz gráfica y soporte para todas las regiones del Perú.

---

## Tabla de contenidos

- [Características](#características)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Inicio rápido con run.bat](#inicio-rápido-con-runbat)
- [Configuración](#configuración)
- [Uso](#uso)
- [Estructura de salida](#estructura-de-salida)
- [Arquitectura del proyecto](#arquitectura-del-proyecto)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Solución de problemas](#solución-de-problemas)

---

## Características

- Scraping de las 25 regiones del Perú disponibles en SENAMHI
- Soporte para los 4 tipos de estación: Meteorológica Convencional, Meteorológica Automática, Hidrológica Convencional e Hidrológica Automática
- Descarga automática de CSV por mes para cada estación seleccionada
- Interfaz gráfica (CustomTkinter) y modo consola
- Manejo automático del captcha Cloudflare Turnstile mediante navegador real
- Detección y manejo de errores del servidor PHP, tablas vacías y meses sin datos
- Organización automática de archivos por región, tipo y nombre de estación
- Reutilización de sesión de navegador para optimizar tiempos de descarga
- Interrupción limpia con Ctrl+C

---

## Requisitos

| Componente | Versión mínima |
|---|---|
| Python | 3.10+ |
| Microsoft Edge | Cualquier versión reciente |
| msedgedriver | Debe coincidir con la versión de Edge instalada |
| Sistema operativo | Windows 10/11 |

### Dependencias Python

```
requests
beautifulsoup4
playwright
customtkinter
```

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/YamilV18/ScrappyDoo---SENAMHI-SCRAPER.git
cd ScrappyDoo---SENAMHI-SCRAPER
```

### 2. Verificar la ruta de msedge.exe

El script busca el ejecutable de Edge en las siguientes rutas por defecto:

```
C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
C:\Program Files\Microsoft\Edge\Application\msedge.exe
```

Si Edge está instalado en una ruta diferente, actualizar la lista `EDGE_PATHS` en la clase `SenamhiScraper`:

```python
EDGE_PATHS = [
    r'C:\ruta\personalizada\msedge.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
]
```

> Para la instalación manual de dependencias sin usar `run.bat`, ver la sección [Instalación manual](#instalación-manual) al final del documento.

---

## Inicio rápido con run.bat

La forma más sencilla de ejecutar el proyecto es mediante el archivo `run.bat` incluido, que automatiza todo el proceso de configuración:

```
run.bat
```

El script realiza automáticamente los siguientes pasos en orden:

| Paso | Acción |
|------|--------|
| 1 | Verifica si Edge ya está corriendo en modo depuración en el puerto `9222`. Si no, lo abre automáticamente. |
| 2 | Comprueba que Python 3.10+ esté instalado y disponible en el PATH. |
| 3 | Crea el entorno virtual `venv/` si no existe. |
| 4 | Instala o actualiza las dependencias (`requests`, `beautifulsoup4`, `playwright`, `customtkinter`). |
| 5 | Verifica e instala los drivers de Playwright para Edge. |
| 6 | Lanza la aplicación ejecutando `main.py`. |

### Requisitos para run.bat

- Python 3.10+ agregado al `PATH` del sistema
- Microsoft Edge instalado
- Conexión a internet (solo en la primera ejecución para descargar dependencias)

### Primera ejecución

En la primera ejecución el proceso puede tardar unos minutos mientras se instalan las dependencias y los drivers de Playwright. Las ejecuciones posteriores son inmediatas ya que el entorno virtual queda guardado localmente.

```
====================================================
  SENAMHI SCRAPER - VERIFICADOR DE ENTORNO
====================================================
[OK] Sesion de Edge detectada en puerto 9222.
[*] Verificando dependencias...
[*] Verificando drivers de navegacion...
====================================================
  INICIANDO APLICACION...
====================================================
```

### Si el captcha no se activa automáticamente

En ocasiones el widget de verificación Cloudflare Turnstile no se activa solo al navegar a la pestaña Tabla. En ese caso:

1. Observar la ventana de Edge que abrió el programa.
2. Si aparece el widget de verificación sin completarse, hacer clic en él manualmente para resolverlo.
3. Una vez verificado, el programa continuará la descarga de forma automática sin necesidad de ninguna acción adicional.

> Esto suele ocurrir en la primera ejecución o cuando la sesión de Edge lleva mucho tiempo inactiva.

### Cerrar el entorno al terminar

Una vez que el programa finalice o se cierre, la instancia de Edge que se abrió en modo depuración puede cerrarse manualmente:

1. Cerrar la ventana de Edge que abrió `run.bat`.
2. O bien, ejecutar en una terminal:

```cmd
taskkill /f /im msedge.exe
```

> **Nota:** Cerrar Edge no elimina el perfil de depuración en `C:\edge-debug-profile`. En la próxima ejecución de `run.bat` el entorno se reutilizará directamente.

### Si la aplicación se detiene inesperadamente

El bat mostrará el mensaje `[!] La aplicacion se detuvo inesperadamente.` y esperará una tecla antes de cerrar, permitiendo leer el error en consola.

---

## Configuración

### Puerto de depuración remota

Por defecto el scraper usa el puerto `9222` para conectarse a Edge. Si ese puerto está ocupado, cambiarlo al instanciar el scraper:

```python
scraper = SenamhiScraper(puerto=9333)
```

### Perfil de Edge

El scraper crea un perfil temporal de Edge en `C:\edge-debug-profile`. Para usar una ruta diferente:

```python
scraper = SenamhiScraper(perfil=r'D:\mi-perfil-edge')
```

### Carpeta de salida

Por defecto los CSV se guardan en `csv_output/` dentro del directorio de ejecución. Personalizable al instanciar:

```python
scraper = SenamhiScraper(carpeta_salida=r'D:\datos_senamhi')
```

---

## Uso

### Interfaz gráfica

```bash
python main_gui.py
```

1. Al iniciar, la barra lateral izquierda cargará automáticamente las 25 regiones disponibles.
2. Hacer clic en una región para cargar sus estaciones.
3. Marcar las estaciones a descargar usando los checkboxes.
4. Presionar **Descargar Selección**.
5. Edge se abrirá automáticamente. El captcha de Cloudflare se resuelve solo al navegar a la pestaña Tabla.
6. La descarga continúa automáticamente por cada mes disponible de cada estación seleccionada.

### Modo consola

```bash
python main_console.py
```

El menú permite:

```
1. Seleccionar región
2. Ver tipos de estación
3. Ver estaciones de la región actual
4. Descargar CSV de estaciones
   ├── 1. Todas las estaciones de la región
   ├── 2. Selección manual por número
   └── 3. Filtrar por tipo de estación
0. Salir
```

### Uso programático

```python
from senamhi_metadata import SenamhiMetadata
from senamhi_scraper import SenamhiScraper

# Obtener estaciones de una región
meta      = SenamhiMetadata()
estaciones = meta.obtener_estaciones('puno')

# Filtrar solo estaciones meteorológicas convencionales
convencionales = [
    e for e in estaciones
    if e['tipo'] == 'Estación Meteorológica Convencional'
]

# Descargar
scraper = SenamhiScraper(carpeta_salida='csv_output')
scraper.exportar_estaciones(convencionales)
```

---

## Estructura de salida

Los archivos se organizan automáticamente de la siguiente manera:

```
csv_output/
└── AMAZONAS/
    ├── ESTACIÓN METEOROLÓGICA CONVENCIONAL/
    │   ├── CHACHAPOYAS - 106011/
    │   │   └── data/
    │   │       ├── 106011_202001.csv
    │   │       ├── 106011_202002.csv
    │   │       └── ...
    │   └── SANTA MARIA DE NIEVA - 104060/
    │       └── data/
    │           ├── 104060_202001.csv
    │           └── ...
    ├── ESTACIÓN METEOROLÓGICA AUTOMÁTICA/
    ├── ESTACIÓN HIDROLÓGICA CONVENCIONAL/
    └── ESTACIÓN HIDROLÓGICA AUTOMÁTICA/
```

### Formato de los CSV

**Estaciones convencionales:**
```
Fuente: SENAMHI / DRD,Leyenda: ...
Estación : CHACHAPOYAS,...
Departamento :,AMAZONAS,Provincia :,...
AÑO / MES / DÍA,TEMPERATURA (°C),...
MAX,MIN,TOTAL
2026-04-01,24.5,12.3,85.2,0.0
```

**Estaciones automáticas:**
```
Fuente: SENAMHI / DRD,Leyenda: ...
Estación : QUISCA,...
AÑO / MES / DÍA,HORA,TEMPERATURA (°C),...
01/04/2026,00:00,15.9,S/D,...
```

---

## Arquitectura del proyecto

```
senamhi-scraper/
├── run.bat                # Inicio rápido — verifica entorno y lanza la app
├── main.py                # Punto de entrada principal
├── main_console.py        # Punto de entrada alternativa en modo consola
├── senamhi_metadata.py    # Clase SenamhiMetadata (scraping de regiones y estaciones)
├── senamhi_scraper.py     # Clase SenamhiScraper (descarga de CSV con Playwright)
├── requirements.txt
├── .gitignore
└── README.md
```

### Clases principales

**`SenamhiMetadata`** — scraping liviano con `requests` + `BeautifulSoup`:
- `obtener_regiones()` → lista de 25 regiones con nombre y código `dp`
- `obtener_tipos_estacion()` → 4 tipos disponibles
- `obtener_estaciones(dp)` → estaciones normalizadas de una región

**`SenamhiScraper`** — automatización con Playwright + Edge:
- `iniciar_sesion()` / `cerrar_sesion()` → gestión del navegador
- `exportar_estacion(estacion)` → descarga todos los meses de una estación
- `exportar_estaciones(estaciones)` → itera sobre una lista reutilizando Edge

---

## Limitaciones conocidas

- **Solo Windows:** el scraper lanza Microsoft Edge mediante su ruta de instalación en Windows. No compatible con Linux/macOS en la versión actual.
- **Captcha Turnstile:** requiere que Edge sea detectado como navegador humano. El perfil temporal `C:\edge-debug-profile` no debe tener extensiones que interfieran.
- **Errores PHP del servidor:** algunas combinaciones de estación/mes devuelven errores PHP desde el servidor de SENAMHI (`Fatal error`, `DivisionByZeroError`). Cuando el error coexiste con datos válidos, el scraper los rescata de todas formas. Cuando no hay datos, el mes se registra como no disponible.
- **Meses sin datos:** el ComboBox de SENAMHI solo muestra meses con al menos un registro. Sin embargo, algunos meses seleccionables devuelven tablas vacías.
- **Un navegador a la vez:** el puerto de depuración remota solo admite una instancia de Edge simultánea.

---

## Solución de problemas

### Edge no arranca o no responde en el puerto 9222

Verificar que no haya otra instancia de Edge usando el mismo puerto:

```bash
netstat -ano | findstr :9222
```

Si hay un proceso ocupando el puerto, cerrarlo desde el Administrador de tareas o cambiar el puerto en la configuración.

### `SessionNotCreatedException` al iniciar Edge

Asegurarse de que **Edge esté completamente cerrado** antes de ejecutar el script. El perfil `C:\edge-debug-profile` no puede estar en uso por otra instancia.

### El captcha no se resuelve automáticamente

El captcha Cloudflare Turnstile se resuelve solo cuando Edge es detectado como navegador humano legítimo. Si falla:

1. Verificar que se está usando `connect_over_cdp` y no `launch` de Playwright.
2. Confirmar que Edge fue iniciado con `--remote-debugging-port=9222`.
3. Esperar a que el widget Turnstile complete la verificación antes de interactuar.

### CSV descargados con contenido HTML en lugar de datos

Esto ocurre cuando el POST al endpoint se hace sin un token Turnstile válido. Solución: dejar que el script gestione la navegación completa (Gráfico → Tabla → selección de mes) sin intervenir manualmente.

### `ECONNREFUSED ::1:9222` al conectar Playwright

Windows resolvió `localhost` como IPv6 (`::1`) en lugar de IPv4. El script ya usa `127.0.0.1` explícitamente, pero si el error persiste, editar `C:\Windows\System32\drivers\etc\hosts` y asegurarse de que la línea `127.0.0.1 localhost` esté presente y sin comentar.

---

## Instalación manual

Si se prefiere no usar `run.bat`, los pasos equivalentes en terminal son:

```bash
# 1. Crear entorno virtual
python -m venv venv
venv\Scripts\activate

# 2. Instalar dependencias
pip install --upgrade pip
pip install requests beautifulsoup4 playwright customtkinter

# 3. Instalar drivers de Playwright para Edge
playwright install msedge

# 4. Lanzar Edge en modo depuración (en una terminal separada)
msedge.exe --remote-debugging-port=9222 --user-data-dir="C:\edge-debug-profile"

# 5. Ejecutar la aplicación
python main.py
```

---

## Licencia

MIT License — libre para uso académico y personal. Los datos descargados pertenecen a SENAMHI y su uso es responsabilidad del usuario, conforme al aviso legal de la plataforma.
