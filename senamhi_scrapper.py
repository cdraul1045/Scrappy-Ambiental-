import os
import re
import time
import signal
import threading
import subprocess
import urllib.request
import urllib.error
from queue import Queue
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

class SenamhiScraper:
    """
    Scraper para descargar datos hidrometeorológicos de SENAMHI.
    
    Uso básico:
        scraper = SenamhiScraper(carpeta_salida='csv_output', puerto=9222)
        scraper.exportar_estaciones(estaciones)
    """

    URL_BASE_TABLA  = 'https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php'
    URL_BASE_MAPA   = 'https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/'
    ENDPOINT        = 'https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/__dt_est_tp_0s3n@mH1.php'
    EDGE_PATHS      = [
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    ]

    def __init__(self, carpeta_salida='csv_output', puerto=9222,
                 perfil=r'C:\edge-debug-profile'):
        self.carpeta_salida = carpeta_salida
        self.puerto         = puerto
        self.perfil         = perfil
        self._interrumpido  = False
        self._proceso_edge  = None
        self._browser        = None
        self._playwright     = None

        # Registrar Ctrl+C
        signal.signal(signal.SIGINT, self._manejador_senal)

    def iniciar_sesion(self):
        """Abre Edge una sola vez para toda la sesión"""
        self._playwright   = sync_playwright().start()
        self._proceso_edge = self._lanzar_edge()
        time.sleep(2)
        self._browser = self._playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{self.puerto}"
        )
        print("[SESIÓN] Edge iniciado y conectado")

    def cerrar_sesion(self):
        """Cierra Edge al finalizar todas las descargas"""
        try:
            if self._browser:
                self._browser.close()
        except:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except:
            pass
        self._cerrar_edge()
        print("[SESIÓN] Edge cerrado")    

    # ══════════════════════════════════════════════════════════════════════
    # Señales
    # ══════════════════════════════════════════════════════════════════════

    def _manejador_senal(self, sig, frame):
        print("\n[!] Interrupción detectada, cerrando limpiamente...")
        self._interrumpido = True

    # ══════════════════════════════════════════════════════════════════════
    # Edge
    # ══════════════════════════════════════════════════════════════════════

    def _edge_corriendo(self):
        try:
            urllib.request.urlopen(
                f'http://127.0.0.1:{self.puerto}/json/version', timeout=2
            )
            return True
        except:
            return False

    def _lanzar_edge(self):
        if self._edge_corriendo():
            print(f"[OK] Edge ya estaba corriendo en puerto {self.puerto}")
            return None

        edge_path = next((p for p in self.EDGE_PATHS if os.path.exists(p)), None)
        if not edge_path:
            raise Exception("No se encontró msedge.exe")

        print(f"[EDGE] Lanzando en puerto {self.puerto}...")
        proceso = subprocess.Popen(
            [
                edge_path,
                f'--remote-debugging-port={self.puerto}',
                f'--remote-debugging-address=127.0.0.1',
                f'--user-data-dir={self.perfil}',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-extensions',
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        for intento in range(20):
            time.sleep(1)
            if proceso.poll() is not None:
                raise Exception(f"Edge se cerró inesperadamente")
            if self._edge_corriendo():
                print(f"    Edge listo tras {intento+1}s")
                return proceso

        raise Exception("Edge no respondió en el tiempo esperado")

    def _cerrar_edge(self):
        if self._proceso_edge:
            print("[EDGE] Cerrando...")
            self._proceso_edge.terminate()
            self._proceso_edge = None

    # ══════════════════════════════════════════════════════════════════════
    # URLs
    # ══════════════════════════════════════════════════════════════════════

    def _url_grafico(self, estacion):
        return (
            f"{self.URL_BASE_TABLA}"
            f"?cod={estacion['codigo']}"
            f"&estado={estacion['estado']}"
            f"&tipo_esta={estacion['ico']}"
            f"&cate={estacion['categoria']}"
            f"&cod_old={estacion.get('codigo_old') or ''}"
            f"#grafico"
        )

    def _url_tabla(self, estacion):
        return self._url_grafico(estacion).replace('#grafico', '#tabla')

    # ══════════════════════════════════════════════════════════════════════
    # Navegación
    # ══════════════════════════════════════════════════════════════════════

    def _ir_a_pestana_tabla(self, page):
        print("    Haciendo clic en pestaña Tabla...")
        selectores = [
            'a[href*="#tabla"]',
            'a:has-text("Tabla")',
            '[data-tab="tabla"]',
            '#tabla-tab',
            '.nav-link:has-text("Tabla")',
        ]
        for selector in selectores:
            try:
                elemento = page.locator(selector).first
                if elemento.is_visible(timeout=2000):
                    elemento.click()
                    print(f"    Selector: {selector}")
                    return
            except:
                continue
        try:
            page.get_by_text("Tabla", exact=True).first.click()
            return
        except:
            pass
        raise Exception("No se encontró la pestaña Tabla")

    def _esperar_token(self, page, timeout=60):
        inicio = time.time()
        while time.time() - inicio < timeout:
            tokens = page.evaluate("""
                () => Array.from(
                    document.querySelectorAll('input[name="cf-turnstile-response"]')
                ).map(el => el.value)
            """)
            valor = tokens[0] if tokens else ''
            if valor and valor not in ('', 'None', 'undefined') and len(valor) > 20:
                return valor
            time.sleep(0.2)
        raise Exception("Timeout esperando token Turnstile")

    def _esperar_iframe(self, page, timeout=30):
        inicio = time.time()
        while time.time() - inicio < timeout:
            try:
                frame = page.frame(name='contenedor')
                if frame:
                    contenido = frame.content()
                    if ('dataTable' in contenido or 'tableHidden' in contenido):
                        if frame.evaluate("() => document.readyState") == 'complete':
                            return frame
            except:
                pass
            time.sleep(0.2)
        raise Exception("Timeout esperando iframe")
    
    def _validar_contenido_iframe(self, frame, filtro_valor, estacion):
        try:
            contenido = frame.content()

            # Captcha inválido
            if 'CAPTCHA es inválido' in contenido or 'turnstile' in contenido.lower():
                return 'captcha', 'Captcha inválido en iframe'

            # Verificar error PHP
            error_php = None
            if 'Fatal error' in contenido or 'Uncaught' in contenido:
                match     = re.search(r'((?:Fatal error|Uncaught \w+):.*?)(?:<br|Stack|$)',
                                    contenido, re.IGNORECASE)
                error_php = match.group(1).strip() if match else 'Error PHP desconocido'

            es_automatica  = estacion.get('estado') == 'AUTOMATICA'
            filas_cabecera = 1 if es_automatica else 2

            # Evaluar directamente en el DOM del iframe
            resultado = frame.evaluate(f"""
                () => {{
                    const info = {{
                        tiene_dataTable:   false,
                        tiene_tableHidden: false,
                        filas_datos:       0,
                        filas_cabecera:    0,
                        debug:             []
                    }};

                    // Verificar dataTable en el documento del iframe
                    const dataTable = document.getElementById('dataTable');
                    info.tiene_dataTable = !!dataTable;
                    info.debug.push('dataTable: ' + !!dataTable);

                    // Verificar tableHidden
                    const tableHidden = document.getElementById('tableHidden');
                    info.tiene_tableHidden = !!tableHidden;
                    info.debug.push('tableHidden: ' + !!tableHidden);

                    if (tableHidden) {{
                        info.filas_cabecera = tableHidden.getElementsByTagName('tr').length;
                        info.debug.push('filas_cabecera: ' + info.filas_cabecera);
                    }}

                    if (dataTable) {{
                        // Solo filas con <td> (no <th>)
                        const filas = Array.from(dataTable.getElementsByTagName('tr'))
                            .filter(tr => tr.querySelectorAll('td').length > 0);
                        info.filas_datos = filas.length;
                        info.debug.push('filas_datos: ' + info.filas_datos);
                    }}

                    return info;
                }}
            """)

            # Mostrar debug para diagnóstico
            print(f"    [DOM] {' | '.join(resultado['debug'])}")

            tiene_tabla = resultado['tiene_dataTable'] or resultado['tiene_tableHidden']
            filas_datos = resultado['filas_datos']
            tiene_datos = filas_datos > 0

            # Verificar cabeceras inesperadas
            if resultado['filas_cabecera'] not in (0, filas_cabecera):
                print(f"    [!] Cabeceras inesperadas: "
                    f"{resultado['filas_cabecera']} (esperado {filas_cabecera})")

            if error_php:
                if tiene_datos:
                    print(f"    [!] Error PHP con {filas_datos} filas rescatables: {error_php[:80]}")
                    return 'ok_con_error', error_php
                else:
                    return 'error_servidor', error_php

            if not tiene_tabla or not tiene_datos:
                return 'vacio', f'Sin filas de datos (filas encontradas: {filas_datos})'

            return 'ok', ''

        except Exception as e:
            return 'error_servidor', str(e)

    def _select_y_esperar_iframe(self, page, filtro_valor, timeout=30):
        contenido_anterior = ""
        try:
            frame = page.frame(name='contenedor')
            if frame:
                contenido_anterior = frame.content()
        except:
            pass

        page.select_option('select[name="CBOFiltro"]', filtro_valor)

        inicio = time.time()
        fase   = 'esperando_cambio'
        while time.time() - inicio < timeout:
            try:
                frame = page.frame(name='contenedor')
                if not frame:
                    time.sleep(0.2)
                    continue
                contenido = frame.content()

                # Detectar captcha inválido y recargar automáticamente
                if 'CAPTCHA es inválido' in contenido or 'captcha' in contenido.lower():
                    print("    [!] Captcha inválido detectado en iframe, recargando...")
                    return None  # señal de reintento

                if fase == 'esperando_cambio':
                    if contenido != contenido_anterior:
                        fase = 'esperando_datos'

                elif fase == 'esperando_datos':
                    # Verificar si ya tiene respuesta definitiva del servidor
                    # (sea error, vacío u ok)
                    tiene_respuesta = (
                        'dataTable'       in contenido or
                        'tableHidden'     in contenido or
                        'Fatal error'     in contenido or
                        'CAPTCHA'         in contenido or
                        frame.evaluate("() => document.readyState") == 'complete'
                    )
                    if tiene_respuesta and filtro_valor[:4] in contenido or \
                    'Fatal error' in contenido or 'CAPTCHA' in contenido:
                        return frame
            except:
                pass
            time.sleep(0.2)
        raise Exception(f"Timeout iframe para {filtro_valor}")

    # ══════════════════════════════════════════════════════════════════════
    # Extracción
    # ══════════════════════════════════════════════════════════════════════

    def _extraer_csv(self, frame, filtro_valor):
        csv_string = frame.evaluate("""
            () => {
                const csv = [];
                const tableHidden = document.getElementById("tableHidden");
                const tableData   = document.getElementById("dataTable");
                const container   = document.getElementById("container");

                if (container) {
                    const lados = container.getElementsByTagName('div');
                    if (lados.length >= 2) {
                        const izq = lados[0].innerText.trim().replace(/\\s+/g, ' ');
                        const der = lados[1].innerText.trim().replace(/\\s+/g, ' ');
                        csv.push(`${izq},${der}`);
                    }
                }
                if (tableHidden) {
                    const rows = tableHidden.getElementsByTagName('tr');
                    for (let r of rows) {
                        const cols = r.querySelectorAll('td,th');
                        csv.push(Array.from(cols).map(
                            td => td.innerText.trim().replace(/\\s+/g, ' ')
                        ).join(','));
                    }
                }
                if (tableData) {
                    const rows = tableData.getElementsByTagName('tr');
                    for (let r of rows) {
                        const cols = r.querySelectorAll('td,th');
                        csv.push(Array.from(cols).map(
                            td => td.innerText.trim().replace(/\\s+/g, ' ')
                        ).join(','));
                    }
                }
                return csv.join('\\n');
            }
        """)

        anio = filtro_valor[:4]
        mes  = str(int(filtro_valor[4:])).zfill(2)
        
        formatos_validos = [
            f"{anio}-{mes}",       # 2026-04  (convencionales)
            f"{anio}/{mes}",       # 2026/04  (automáticas)
            f"/{anio}",            # /2026    (algunas automáticas)
            f"{mes}/{anio}",       # 04/2026
            f"{mes}-{anio}",       # 04-2026
        ]
        formatos_dia = [
            rf"\d{{2}}/{mes}/{anio}",   # dd/mm/yyyy → 01/04/2026
            rf"\d{{2}}-{mes}-{anio}",   # dd-mm-yyyy → 01-04-2026
            rf"\d{{2}}/{mes}/{anio[2:]}",# dd/mm/yy  → 01/04/26
        ]

        if any(f in csv_string for f in formatos_validos):
            return csv_string

        for patron in formatos_dia:
            if re.search(patron, csv_string):
                return csv_string

        raise Exception(
            f"Mes incorrecto en CSV. "
            f"Esperado {anio}-{mes} en alguno de los formatos conocidos.\n"
            f"Primeras 3 líneas del CSV:\n" +
            '\n'.join(csv_string.splitlines()[:3])
        )

    # ══════════════════════════════════════════════════════════════════════
    # Worker de escritura
    # ══════════════════════════════════════════════════════════════════════

    def _iniciar_worker(self):
        cola = Queue()

        def worker():
            while True:
                item = cola.get()
                if item is None:
                    cola.task_done()
                    break
                nombre, contenido = item
                try:
                    with open(nombre, 'w', encoding='utf-8-sig') as f:
                        f.write(contenido)
                    print(f"    [DISCO] {os.path.basename(nombre)}")
                except Exception as e:
                    print(f"    [DISCO] Error: {e}")
                finally:
                    cola.task_done()

        hilo = threading.Thread(target=worker, daemon=True)
        hilo.start()
        return cola, hilo

    def _cerrar_worker(self, cola, hilo):
        cola.put(None)
        cola.join()
        hilo.join(timeout=5)

    def _obtener_pendientes(self, estacion, opciones, carpeta):
        """
        Compara los meses disponibles contra los archivos ya descargados.
        Retorna (pendientes, omitidos).
        """
        pendientes = []
        omitidos   = []
        for filtro_valor in opciones:
            nombre = os.path.join(carpeta, f"{estacion['codigo']}_{filtro_valor}.csv")
            if os.path.exists(nombre) and os.path.getsize(nombre) > 0:
                omitidos.append(filtro_valor)
            else:
                pendientes.append(filtro_valor)
        return pendientes, omitidos

    def _construir_carpeta(self, estacion, carpeta_salida=None):
        if carpeta_salida:
            return carpeta_salida
        tipo_estacion   = estacion['tipo'].upper()
        nombre_estacion = f"{estacion['nombre'].upper()} - {estacion['codigo']}"
        return os.path.join(self.carpeta_salida, tipo_estacion, nombre_estacion, 'data')

    # ══════════════════════════════════════════════════════════════════════
    # Exportar una estación
    # ══════════════════════════════════════════════════════════════════════

    def exportar_estacion(self, estacion, carpeta_salida=None):
        
        sesion_temporal = self._browser is None
        carpeta     = self._construir_carpeta(estacion, carpeta_salida)
        url_grafico = self._url_grafico(estacion)

        os.makedirs(carpeta, exist_ok=True)

        # ── PASO 1: Verificación rápida sin abrir el navegador ─────────────────
        # Obtener lista de meses disponibles via requests (sin Playwright)
        print(f"\n[PRE] Verificando meses ya descargados para {estacion['nombre']}...")
        opciones_previas = self._obtener_opciones_sin_navegador(estacion)

        if opciones_previas:
            pendientes, omitidos = self._obtener_pendientes(estacion, opciones_previas, carpeta)
            print(f"  Meses conocidos    : {len(opciones_previas)}")
            print(f"  Ya descargados     : {len(omitidos)}")
            print(f"  Pendientes         : {len(pendientes)}")

            if not pendientes:
                print("  [OK] Estación completamente descargada, omitiendo navegador.")
                return
        else:
            # No se pudo obtener opciones sin navegador, continuar normalmente
            pendientes = None
            omitidos   = []

        # ── PASO 2: Abrir navegador solo si hay pendientes ─────────────────────
        cola, hilo = self._iniciar_worker()
        try:
            context = self._browser.contexts[0]
            page    = context.new_page()

            print(f"\n[1] Cargando: {url_grafico}")
            page.goto(url_grafico, wait_until='domcontentloaded')
            time.sleep(2)

            print("[2] Navegando a pestaña Tabla...")
            self._ir_a_pestana_tabla(page)

            print("[3] Esperando Turnstile...")
            self._esperar_token(page)

            html    = page.content()
            match   = re.search(r'(\d+)\s*msnm', html, re.IGNORECASE)
            altitud = match.group(1) if match else ''
            print(f"[4] Altitud: {altitud} msnm")

            soup   = BeautifulSoup(html, 'html.parser')
            select = soup.find('select', {'name': 'CBOFiltro'})
            if not select:
                raise Exception("ComboBox no encontrado")

            opciones = [o.get('value') for o in select.find_all('option')]

            # Re-verificar con opciones actualizadas del navegador
            pendientes, omitidos = self._obtener_pendientes(estacion, opciones, carpeta)

            # Detectar meses nuevos respecto a la verificación previa
            if opciones_previas:
                nuevos = [m for m in opciones if m not in opciones_previas]
                if nuevos:
                    print(f"  [+] Meses nuevos detectados: {nuevos}")

            print(f"[5] Meses disponibles  : {len(opciones)}")
            print(f"    Ya descargados     : {len(omitidos)}")
            print(f"    Pendientes         : {len(pendientes)}")


            if not pendientes:
                print("    [OK] Estación completamente descargada, omitiendo.")
                page.close()
                self._cerrar_worker(cola, hilo)
                return


            errores = []
            tiempos = []

            resultados = {
                'ok':             [],
                'vacio':          [],
                'error_servidor': [],
                'error_scraper':  [],
            }
            MAX_REINTENTOS = 3

            for i, filtro_valor in enumerate(pendientes):
                if self._interrumpido:
                    print("\n[!] Interrumpido")
                    break
                print(f"\n--- [{i+1}/{len(pendientes)}] {filtro_valor} ---")
                t0 = time.time()
                exito = False
                for intento in range(MAX_REINTENTOS):
                    try:
                        if intento > 0:
                            print(f"    Reintento {intento}/{MAX_REINTENTOS}...")
                            page.goto(url_grafico, wait_until='domcontentloaded')
                            time.sleep(2)
                            self._ir_a_pestana_tabla(page)
                            self._esperar_token(page)

                        frame = self._select_y_esperar_iframe(page, filtro_valor)
                        if frame is None:
                            continue

                        # Validar contenido antes de extraer
                        estado, msg = self._validar_contenido_iframe(frame, filtro_valor, estacion)

                        if estado == 'captcha':
                            print(f"    [!] Captcha → reintentando...")
                            continue

                        if estado == 'error_servidor':
                            print(f"    [SERVER] {msg}")
                            resultados['error_servidor'].append({
                                'mes': filtro_valor, 'error': msg
                            })
                            exito = True
                            break

                        if estado == 'vacio':
                            print(f"    [VACÍO] Sin datos para {filtro_valor}")
                            resultados['vacio'].append({'mes': filtro_valor})
                            exito = True
                            break

                        # 'ok' y 'ok_con_error' → intentar extraer datos
                        if estado in ('ok', 'ok_con_error'):
                            try:
                                csv = self._extraer_csv(frame, filtro_valor)
                                if not csv or len(csv) < 10:
                                    raise Exception("CSV vacío tras extracción")

                                nombre = os.path.join(
                                    carpeta, f"{estacion['codigo']}_{filtro_valor}.csv"
                                )
                                cola.put((nombre, csv))
                                t = round(time.time() - t0, 2)
                                tiempos.append(t)

                                if estado == 'ok_con_error':
                                    # Guardado con advertencia
                                    resultados['ok'].append({
                                        'mes': filtro_valor, 'tiempo': t,
                                        'advertencia': msg  # error PHP registrado
                                    })
                                    print(f"    [OK*] {len(csv.splitlines())} filas en {t}s (con error PHP)")
                                else:
                                    resultados['ok'].append({'mes': filtro_valor, 'tiempo': t})
                                    print(f"    [OK] {len(csv.splitlines())} filas en {t}s")

                                exito = True
                                break

                            except Exception as e:
                                print(f"    [!] Extracción fallida: {e}")
                                if intento == MAX_REINTENTOS - 1:
                                    resultados['error_scraper'].append({
                                        'mes': filtro_valor, 'error': str(e)
                                    })

                    except Exception as e:
                        print(f"    [!] Intento {intento+1} fallido: {e}")
                        if intento == MAX_REINTENTOS - 1:
                            resultados['error_scraper'].append({
                                'mes': filtro_valor, 'error': str(e)
                            })

                if not exito and not self._interrumpido:
                    print(f"    [X] {filtro_valor} no se pudo descargar tras {MAX_REINTENTOS} intentos")

            self._cerrar_worker(cola, hilo)

            total = len(opciones)
            print(f"\n=== Resumen: {estacion['nombre']} ===")
            ok_limpios    = [r for r in resultados['ok'] if 'advertencia' not in r]
            ok_con_aviso  = [r for r in resultados['ok'] if 'advertencia' in r]
            print(f"  ✓ Descargados        : {len(ok_limpios)}/{total}")
            print(f"  ✓ Descargados (PHP*) : {len(ok_con_aviso)}/{total}")
            print(f"  ~ Vacíos             : {len(resultados['vacio'])}/{total}")
            print(f"  ✗ Error servidor     : {len(resultados['error_servidor'])}/{total}")
            print(f"  ✗ Error scraper      : {len(resultados['error_scraper'])}/{total}")

            if ok_con_aviso:
                print(f"\n  Meses con error PHP pero datos rescatados:")
                for r in ok_con_aviso:
                    print(f"    • {r['mes']}: {r['advertencia'][:80]}")

            if resultados['vacio']:
                print(f"\n  Meses sin datos:")
                for r in resultados['vacio']:
                    print(f"    • {r['mes']}")

            if resultados['error_servidor']:
                print(f"\n  Errores del servidor:")
                for r in resultados['error_servidor']:
                    print(f"    • {r['mes']}: {r['error'][:80]}")

            if resultados['error_scraper']:
                print(f"\n  Errores del scraper:")
                for r in resultados['error_scraper']:
                    print(f"    • {r['mes']}: {r['error'][:80]}")

            if tiempos:
                print(f"\n=== Estadísticas: {estacion['nombre']} ===")
                print(f"  Procesados : {len(tiempos)}/{len(opciones)}")
                print(f"  Promedio   : {round(sum(tiempos)/len(tiempos), 2)}s")
                print(f"  Total      : {round(sum(tiempos), 2)}s")
            if errores:
                print(f"\n=== Errores ({len(errores)}) ===")
                for err in errores:
                    print(f"  {err['mes']}: {err['error']}")

            print("\n=== Proceso finalizado ===")
            page.close()  # solo cerrar la pestaña, no el navegador

        except Exception as e:
            print(f"\n[!] Error crítico: {e}")
            self._cerrar_worker(cola, hilo)
        finally:
            # Solo cerrar Edge si fue sesión temporal
            if sesion_temporal:
                self.cerrar_sesion()

    def _obtener_opciones_sin_navegador(self, estacion):
        """
        Obtiene la lista de meses disponibles via requests+BeautifulSoup,
        sin necesidad de abrir el navegador.
        Retorna lista de valores del ComboBox o [] si falla.
        """
        try:
            url = (
                f"https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php"
                f"?cod={estacion['codigo']}"
                f"&estado={estacion['estado']}"
                f"&tipo_esta={estacion['ico']}"
                f"&cate={estacion['categoria']}"
                f"&cod_old={estacion.get('codigo_old') or ''}"
            )
            response = requests.get(url, timeout=10)
            soup     = BeautifulSoup(response.text, 'html.parser')
            select   = soup.find('select', {'name': 'CBOFiltro'})
            if not select:
                return []
            return [o.get('value') for o in select.find_all('option')]
        except Exception as e:
            print(f"  [!] No se pudo obtener opciones sin navegador: {e}")
            return []

    # ══════════════════════════════════════════════════════════════════════
    # Exportar múltiples estaciones
    # ══════════════════════════════════════════════════════════════════════

    def exportar_estaciones(self, estaciones):
        """Exporta múltiples estaciones reutilizando Edge"""
        self.iniciar_sesion()
        try:
            total = len(estaciones)
            for i, estacion in enumerate(estaciones, 1):
                if self._interrumpido:
                    break
                print(f"\n{'='*50}")
                print(f"[{i}/{total}] {estacion['nombre']} ({estacion['codigo']})")
                print(f"{'='*50}")
                self.exportar_estacion(estacion)
            print("\n[FIN] Todas las estaciones procesadas")
        finally:
            self.cerrar_sesion()