from senamhi_metadata import SenamhiMetadata
from senamhi_scrapper import SenamhiScraper
import os

class MenuConsola:
    def __init__(self):
        self.regiones          = []
        self.tipos_estacion    = []
        self.estaciones        = []
        self.region_actual     = None
        self.scraper           = SenamhiScraper()

    def _separador(self, titulo=''):
        print(f"\n{'─'*50}")
        if titulo:
            print(f"  {titulo}")
            print(f"{'─'*50}")

    # ── Menú principal ─────────────────────────────────────────────────────
    def menu_principal(self):
        while True:
            self._separador('SENAMHI — Descarga de datos hidrometeorológicos')
            print("  1. Seleccionar región")
            print("  2. Ver tipos de estación")
            print("  3. Ver estaciones de la región actual")
            print("  4. Descargar CSV de estaciones")
            print("  0. Salir")
            self._separador()

            opcion = input("  Opción: ").strip()

            if opcion == '1':
                self._menu_regiones()
            elif opcion == '2':
                self._ver_tipos()
            elif opcion == '3':
                self._ver_estaciones()
            elif opcion == '4':
                self._menu_descarga()
            elif opcion == '0':
                print("\n  Hasta luego.")
                break
            else:
                print("  [!] Opción no válida")

    # ── Selección de región ────────────────────────────────────────────────
    def _menu_regiones(self):
        if not self.regiones:
            self.regiones = SenamhiMetadata.obtener_regiones()

        self._separador('Regiones disponibles')
        for i, r in enumerate(self.regiones, 1):
            marca = ' ←' if self.region_actual and self.region_actual['dp'] == r['dp'] else ''
            print(f"  {i:2}. {r['nombre']}{marca}")
        self._separador()

        try:
            idx = int(input("  Selecciona región (0 para cancelar): ")) - 1
            if idx == -1:
                return
            if 0 <= idx < len(self.regiones):
                self.region_actual = self.regiones[idx]
                self.estaciones    = []  # limpiar estaciones anteriores
                print(f"\n  [OK] Región seleccionada: {self.region_actual['nombre']}")
            else:
                print("  [!] Número fuera de rango")
        except ValueError:
            print("  [!] Entrada no válida")

    # ── Ver tipos de estación ──────────────────────────────────────────────
    def _ver_tipos(self):
        if not self.tipos_estacion:
            self.tipos_estacion = SenamhiMetadata.obtener_tipos_estacion()

        self._separador('Tipos de estación')
        for t in self.tipos_estacion:
            print(f"  • {t}")

    # ── Ver estaciones ─────────────────────────────────────────────────────
    def _ver_estaciones(self):
        if not self.region_actual:
            print("\n  [!] Primero selecciona una región (opción 1)")
            return

        if not self.estaciones:
            self.estaciones = SenamhiMetadata.obtener_estaciones(
                self.region_actual['dp']
            )

        self._separador(f"Estaciones — {self.region_actual['nombre']}")

        # Agrupar por tipo
        from collections import defaultdict
        por_tipo = defaultdict(list)
        for e in self.estaciones:
            por_tipo[e['tipo']].append(e)

        for tipo, lista in por_tipo.items():
            print(f"\n  [{tipo}] — {len(lista)} estaciones")
            for e in lista:
                print(f"    • {e['nombre']:30} cod: {e['codigo']:10} estado: {e['estado']}")

        print(f"\n  Total: {len(self.estaciones)} estaciones")

    # ── Menú de descarga ───────────────────────────────────────────────────
    def _menu_descarga(self):
        if not self.region_actual:
            print("\n  [!] Primero selecciona una región (opción 1)")
            return

        if not self.estaciones:
            self.estaciones = SenamhiMetadata.obtener_estaciones(
                self.region_actual['dp']
            )

        self._separador('Descarga de CSV')
        print("  1. Descargar todas las estaciones de la región")
        print("  2. Seleccionar estaciones manualmente")
        print("  3. Filtrar por tipo de estación")
        print("  0. Volver")
        self._separador()

        opcion = input("  Opción: ").strip()

        if opcion == '1':
            self._descargar(self.estaciones)
        elif opcion == '2':
            self._seleccionar_estaciones_manual()
        elif opcion == '3':
            self._filtrar_por_tipo()
        elif opcion == '0':
            return
        else:
            print("  [!] Opción no válida")

    def _seleccionar_estaciones_manual(self):
        self._separador('Selección manual de estaciones')
        for i, e in enumerate(self.estaciones, 1):
            print(f"  {i:3}. {e['nombre']:30} ({e['tipo']})")
        self._separador()
        print("  Ingresa los números separados por coma (ej: 1,3,5)")

        entrada = input("  Selección: ").strip()
        try:
            indices    = [int(x.strip()) - 1 for x in entrada.split(',')]
            seleccion  = [self.estaciones[i] for i in indices if 0 <= i < len(self.estaciones)]
            if seleccion:
                self._descargar(seleccion)
            else:
                print("  [!] No se seleccionó ninguna estación válida")
        except ValueError:
            print("  [!] Entrada no válida")

    def _filtrar_por_tipo(self):
        from collections import defaultdict
        por_tipo = defaultdict(list)
        for e in self.estaciones:
            por_tipo[e['tipo']].append(e)

        tipos = list(por_tipo.keys())
        self._separador('Filtrar por tipo')
        for i, t in enumerate(tipos, 1):
            print(f"  {i}. {t} ({len(por_tipo[t])} estaciones)")
        self._separador()

        try:
            idx = int(input("  Selecciona tipo (0 para cancelar): ")) - 1
            if idx == -1:
                return
            if 0 <= idx < len(tipos):
                seleccion = por_tipo[tipos[idx]]
                self._descargar(seleccion)
            else:
                print("  [!] Número fuera de rango")
        except ValueError:
            print("  [!] Entrada no válida")

    def _descargar(self, estaciones):
        self._separador(f'Descargando {len(estaciones)} estaciones')
        for e in estaciones:
            print(f"  • {e['nombre']} ({e['codigo']})")

        confirmar = input("\n  ¿Confirmar descarga? (s/n): ").strip().lower()
        if confirmar != 's':
            print("  Descarga cancelada")
            return

        nombre_region = self.region_actual['nombre'].upper() 
        carpeta_base = os.path.join('csv_output', nombre_region)

        self.scraper.carpeta_salida = carpeta_base
        self.scraper.exportar_estaciones(estaciones)