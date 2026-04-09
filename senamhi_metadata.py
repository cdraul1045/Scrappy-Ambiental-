import requests
from bs4 import BeautifulSoup
import json
import re

# ══════════════════════════════════════════════════════════════════════════════
# Scrapper de metadata (regiones, tipos, estaciones)
# ══════════════════════════════════════════════════════════════════════════════

class SenamhiMetadata:
    URL_PRINCIPAL = 'https://www.senamhi.gob.pe/main.php?dp=amazonas&p=estaciones'
    URL_MAPA      = 'https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/?dp={dp}'

    @staticmethod
    def obtener_regiones():
        print("[META] Obteniendo regiones...")
        response = requests.get(SenamhiMetadata.URL_PRINCIPAL)
        soup     = BeautifulSoup(response.text, 'html.parser')
        dropdown = soup.find('div', {'class': 'dropdown-menu'})
        links    = dropdown.find_all('a', class_='dropdown-item')

        regiones = []
        for link in links:
            href = link.get('href', '')
            if 'dp=' in href:
                dp     = href.split('dp=')[1].split('&')[0]
                nombre = link.get_text(strip=True)
                regiones.append({'nombre': nombre, 'dp': dp})

        print(f"  {len(regiones)} regiones encontradas")
        return regiones

    @staticmethod
    def obtener_tipos_estacion():
        print("[META] Obteniendo tipos de estación...")
        response = requests.get(SenamhiMetadata.URL_PRINCIPAL)
        soup     = BeautifulSoup(response.text, 'html.parser')

        clases = [
            'ico-leyenda-mapa-convencional-m',
            'ico-leyenda-mapa-automatica-m',
            'ico-leyenda-mapa-convencional-h',
            'ico-leyenda-mapa-automatica-h',
        ]
        tipos = []
        for clase in clases:
            div = soup.find('div', class_=clase)
            if div:
                tipos.append(div.get_text(strip=True))

        print(f"  {len(tipos)} tipos encontrados")
        return tipos

    @staticmethod
    def obtener_estaciones(dp):
        print(f"[META] Obteniendo estaciones de '{dp}'...")
        url      = SenamhiMetadata.URL_MAPA.format(dp=dp)
        response = requests.get(url)
        soup     = BeautifulSoup(response.text, 'html.parser')

        script_target = None
        for script in soup.find_all('script', type='text/javascript'):
            if script.string and 'PruebaTest' in script.string:
                script_target = script.string
                break

        if not script_target:
            print(f"  [!] No se encontró PruebaTest para {dp}")
            return []

        match = re.search(
            r'var PruebaTest\s*=\s*(\[.*?\])\s*;', script_target, re.DOTALL
        )
        if not match:
            print(f"  [!] No se pudo extraer el JSON para {dp}")
            return []

        json_raw = match.group(1)

        # Limpiar valores problemáticos antes de parsear
        # 1. Reemplazar valores vacíos sin comillas → null
        json_raw = re.sub(r':\s*,', ': null,', json_raw)
        json_raw = re.sub(r':\s*}', ': null}', json_raw)
        # 2. Eliminar comas finales antes de ] o } (JSON no las permite)
        json_raw = re.sub(r',\s*([}\]])', r'\1', json_raw)
        # 3. Reemplazar NaN e Infinity (válidos en JS pero no en JSON)
        json_raw = re.sub(r':\s*NaN\b', ': null', json_raw)
        json_raw = re.sub(r':\s*Infinity\b', ': null', json_raw)
        json_raw = re.sub(r':\s*-Infinity\b', ': null', json_raw)
        # 4. Eliminar caracteres de control invisibles
        json_raw = re.sub(r'[\x00-\x1f\x7f]', '', json_raw)

        try:
            estaciones = json.loads(json_raw)
        except json.JSONDecodeError as e:
            # Mostrar contexto del error para diagnóstico
            col   = e.colno
            linea = e.lineno
            # Extraer fragmento alrededor del error
            chars  = json_raw.split('\n')
            linea_problematica = chars[linea - 1] if linea <= len(chars) else ''
            print(f"  [!] JSONDecodeError en {dp}: {e.msg} (línea {linea}, col {col})")
            print(f"  [!] Fragmento: ...{linea_problematica[max(0,col-30):col+30]}...")

            # Intento de rescate: parsear estación por estación
            estaciones = SenamhiMetadata._parsear_estaciones_individual(json_raw, dp)

        normalizadas = [SenamhiMetadata._normalizar(e) for e in estaciones]
        print(f"  {len(normalizadas)} estaciones encontradas")
        return normalizadas

    @staticmethod
    def _normalizar_tipo(estacion):
        ico    = estacion.get('ico', '')
        estado = estacion.get('estado', '')

        tipo_base = {'M': 'Meteorológica', 'H': 'Hidrológica'}.get(ico, 'Desconocida')
        subtipo   = 'Automática' if estado == 'AUTOMATICA' else 'Convencional'
        return f'Estación {tipo_base} {subtipo}'

    @staticmethod
    def _normalizar(estacion):
        return {
            'nombre':     estacion['nom'],
            'codigo':     estacion['cod'],
            'codigo_old': estacion.get('cod_old'),
            'categoria':  estacion['cate'],
            'tipo':       SenamhiMetadata._normalizar_tipo(estacion),
            'ico':        estacion.get('ico', 'M'),
            'latitud':    estacion['lat'],
            'longitud':   estacion['lon'],
            'estado':     estacion['estado'],
        }
    
    @staticmethod
    def _parsear_estaciones_individual(json_raw, dp):
        """
        Fallback: extrae cada objeto JSON individualmente
        cuando el array completo no es parseable.
        """
        print(f"  [!] Intentando rescate individual de estaciones...")
        estaciones = []
        # Buscar cada objeto {...} dentro del array
        for i, obj_match in enumerate(re.finditer(r'\{[^{}]+\}', json_raw)):
            obj_str = obj_match.group(0)
            # Limpiar el objeto individual
            obj_str = re.sub(r',\s*([}\]])', r'\1', obj_str)
            obj_str = re.sub(r':\s*,', ': null,', obj_str)
            obj_str = re.sub(r':\s*NaN\b', ': null', obj_str)
            try:
                estacion = json.loads(obj_str)
                estaciones.append(estacion)
            except json.JSONDecodeError as e:
                print(f"  [!] Estación {i+1} omitida: {e.msg} → {obj_str[:80]}")
                continue

        print(f"  [RESCATE] {len(estaciones)} estaciones recuperadas de {dp}")
        return estaciones