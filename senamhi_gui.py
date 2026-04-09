import customtkinter as ctk
from tkinter import messagebox
import threading
import os
from senamhi_metadata import SenamhiMetadata
from senamhi_scrapper import SenamhiScraper

class SenamhiGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SENAMHI - Descarga de Datos Hidrometeorológicos")
        self.geometry("900x600")
        ctk.set_appearance_mode("dark")
        
        self.metadata = SenamhiMetadata()
        self.scraper = SenamhiScraper()
        self.regiones = []
        self.estaciones = []

        # Configuración de Grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar (Regiones) ---
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.lbl_regiones = ctk.CTkLabel(self.sidebar, text="Regiones", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_regiones.pack(pady=10)

        self.regiones_list = ctk.CTkScrollableFrame(self.sidebar, width=180)
        self.regiones_list.pack(expand=True, fill="both", padx=5, pady=5)

        # --- Main Content ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        self.lbl_info = ctk.CTkLabel(self.main_frame, text="Selecciona una región para ver estaciones", font=ctk.CTkFont(size=14))
        self.lbl_info.grid(row=0, column=0, pady=10)

        # Tabla/Lista de estaciones
        self.estaciones_frame = ctk.CTkScrollableFrame(self.main_frame)
        self.estaciones_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.grid(row=2, column=0, pady=10)

        self.btn_descargar_sel = ctk.CTkButton(
            self.button_frame, 
            text="Descargar Selección", 
            command=self._iniciar_descarga_thread, 
            state="disabled"
        )
        self.btn_descargar_sel.pack(side="left", padx=10)

        self.btn_descargar_todo = ctk.CTkButton(
            self.button_frame, 
            text="Descargar Todo (Región)", 
            fg_color="#2c3e50", # Un color distinto para diferenciarlo
            command=self._confirmar_descarga_total, 
            state="disabled"
        )
        self.btn_descargar_todo.pack(side="left", padx=10)

        self.progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=5)

        self.cargar_regiones()

    def cargar_regiones(self):
        self.regiones = self.metadata.obtener_regiones()
        for region in self.regiones:
            btn = ctk.CTkButton(self.regiones_list, text=region['nombre'], 
                               fg_color="transparent", anchor="w",
                               command=lambda r=region: self.seleccionar_region(r))
            btn.pack(fill="x", pady=2)

    def seleccionar_region(self, region):
        self.region_actual = region
        self.lbl_info.configure(text=f"Región: {region['nombre'].upper()}")
        
        # Limpiar estaciones previas del frame
        for widget in self.estaciones_frame.winfo_children():
            widget.destroy()

        # Obtener estaciones de la metadata
        self.estaciones = self.metadata.obtener_estaciones(region['dp'])
        
        # IMPORTANTE: Usaremos una lista simple de tuplas (variable, objeto_estacion)
        # para evitar errores de KeyError con los IDs
        self.lista_check_estaciones = []

        self.btn_descargar_sel.configure(state="normal")
        self.btn_descargar_todo.configure(state="normal")

        for est in self.estaciones:
            var = ctk.BooleanVar()
            # Crear el Checkbox con el nombre y tipo
            cb = ctk.CTkCheckBox(
                self.estaciones_frame, 
                text=f"{est['nombre']} ({est['tipo']})", 
                variable=var
            )
            cb.pack(anchor="w", pady=2, padx=10)
            
            # Guardamos la referencia de la variable y la data de la estación
            self.lista_check_estaciones.append((var, est))

    def _confirmar_descarga_total(self):
        """Muestra el cuadro de confirmación antes de proceder"""
        nombre_reg = self.region_actual['nombre'].upper()
        num_estaciones = len(self.estaciones)
        
        pregunta = f"¿Está seguro que desea descargar las {num_estaciones} estaciones de la región {nombre_reg}?\n\nEste proceso puede tomar varios minutos."
        
        confirmado = messagebox.askyesno("Confirmar Descarga Total", pregunta)
        
        if confirmado:
            # Si confirma, enviamos todas las estaciones de la región al hilo de descarga
            threading.Thread(
                target=self.ejecutar_descarga, 
                args=(self.estaciones,), 
                daemon=True
            ).start()

    def _iniciar_descarga_thread(self):
        """Descarga solo las seleccionadas mediante checkbox"""
        seleccionadas = [est for var, est in self.lista_check_estaciones if var.get()]
        
        if not seleccionadas:
            messagebox.showwarning("Atención", "Seleccione al menos una estación de la lista.")
            return
            
        threading.Thread(
            target=self.ejecutar_descarga, 
            args=(seleccionadas,), 
            daemon=True
        ).start()

    def ejecutar_descarga(self, seleccionadas):
        self.btn_descargar_sel.configure(state="disabled")
        self.btn_descargar_todo.configure(state="disabled")
        total = len(seleccionadas)

        nombre_region = self.region_actual['nombre'].upper()
        self.scraper.carpeta_salida = os.path.join('csv_output', nombre_region)

        # Abrir Edge una sola vez para todas las estaciones
        self.scraper.iniciar_sesion()
        try:
            for i, estacion in enumerate(seleccionadas, 1):
                if self.scraper._interrumpido:
                    break
                self.lbl_info.configure(
                    text=f"Descargando {i}/{total}: {estacion['nombre']}"
                )
                self.progress_bar.set(i / total)
                self.scraper.exportar_estacion(estacion)
        finally:
            self.scraper.cerrar_sesion()

        self.lbl_info.configure(text=f"✓ Descarga completada — {nombre_region}")
        self.btn_descargar_sel.configure(state="normal")
        self.btn_descargar_todo.configure(state="normal")
        self.progress_bar.set(0)

