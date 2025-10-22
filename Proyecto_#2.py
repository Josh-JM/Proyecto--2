# -----------------------------------------------
# Proyecto #2
# Autor: Josue André Menéndez Juárez
# -----------------------------------------------

import os
import json
import uuid
import datetime
import ttkbootstrap as tb
from ttkbootstrap.dialogs import Messagebox, Dialog
from ttkbootstrap.constants import *
from tkinter import simpledialog

# ---------- Rutas principales ----------
RUTA_RAIZ = os.path.abspath(os.path.dirname(__file__))
CARPETA_FS = os.path.join(RUTA_RAIZ, "sistema_virtual")
CARPETA_BLOQUES = os.path.join(CARPETA_FS, "bloques")
ARCHIVO_FAT = os.path.join(CARPETA_FS, "tabla_fat.json")

os.makedirs(CARPETA_BLOQUES, exist_ok=True)

# ---------- Funciones de utilidad ----------
def fecha_actual():
    """Devuelve la fecha y hora actual en formato legible"""
    return datetime.datetime.now().isoformat(sep=' ', timespec='seconds')


# ---------- Gestor de la Tabla FAT ----------
class GestorFAT:
    def __init__(self, ruta_fat=ARCHIVO_FAT):
        self.ruta_fat = ruta_fat
        self._cargar_tabla()

    def _cargar_tabla(self):
        """Carga la tabla FAT desde archivo o la crea si no existe"""
        if os.path.exists(self.ruta_fat):
            with open(self.ruta_fat, "r", encoding="utf-8") as f:
                self.tabla = json.load(f)
        else:
            self.tabla = []
            self._guardar_tabla()

    def _guardar_tabla(self):
        with open(self.ruta_fat, "w", encoding="utf-8") as f:
            json.dump(self.tabla, f, indent=2, ensure_ascii=False)

    def _crear_bloque(self, texto, siguiente=None, fin=False):
        """Crea un bloque de datos en formato JSON"""
        nombre_bloque = str(uuid.uuid4()) + ".json"
        ruta = os.path.join(CARPETA_BLOQUES, nombre_bloque)
        bloque = {
            "datos": texto,
            "siguiente": siguiente,
            "fin": fin
        }
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(bloque, f, indent=2, ensure_ascii=False)
        return ruta

    def _leer_bloque(self, ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)

    def crear_archivo(self, nombre, contenido, propietario="admin"):
        """Crea un archivo y lo divide en bloques de 20 caracteres"""
        for e in self.tabla:
            if e["nombre"] == nombre and not e["papelera"]:
                raise ValueError("Ya existe un archivo con ese nombre activo.")

        bloques = [contenido[i:i+20] for i in range(0, len(contenido), 20)] if contenido else []
        anterior = None
        primer_bloque = None

        for i, texto in enumerate(bloques):
            es_fin = (i == len(bloques) - 1)
            ruta_bloque = self._crear_bloque(texto, fin=es_fin)
            if anterior is not None:
                bloque_prev = self._leer_bloque(anterior)
                bloque_prev["siguiente"] = ruta_bloque
                with open(anterior, "w", encoding="utf-8") as f:
                    json.dump(bloque_prev, f, indent=2, ensure_ascii=False)
            else:
                primer_bloque = ruta_bloque
            anterior = ruta_bloque

        entrada = {
            "id": str(uuid.uuid4()),
            "nombre": nombre,
            "ruta_datos": primer_bloque,
            "papelera": False,
            "tamano": len(contenido),
            "fecha_creacion": fecha_actual(),
            "fecha_modificacion": fecha_actual(),
            "fecha_eliminacion": None,
            "propietario": propietario,
            "permisos": {
                propietario: {"lectura": True, "escritura": True}
            }
        }
        self.tabla.append(entrada)
        self._guardar_tabla()

    def listar_archivos(self, incluir_papelera=False):
        """Devuelve la lista de archivos (activos o con papelera incluida)"""
        if incluir_papelera:
            return list(self.tabla)
        return [e for e in self.tabla if not e["papelera"]]

    def obtener_entrada(self, id_archivo):
        for e in self.tabla:
            if e["id"] == id_archivo:
                return e
        return None

    def leer_contenido(self, entrada, usuario):
        """Lee todo el contenido del archivo verificando permisos"""
        if not self._permite_lectura(entrada, usuario):
            raise PermissionError("No tienes permiso de lectura.")

        ruta = entrada["ruta_datos"]
        if not ruta:
            return ""
        partes = []
        actual = ruta
        while actual:
            bloque = self._leer_bloque(actual)
            partes.append(bloque["datos"])
            if bloque.get("fin", False):
                break
            actual = bloque.get("siguiente")
        return "".join(partes)

    def modificar_archivo(self, entrada, nuevo_contenido, usuario):
        if not self._permite_escritura(entrada, usuario):
            raise PermissionError("No tienes permiso de escritura.")

        self._eliminar_bloques(entrada["ruta_datos"])

        bloques = [nuevo_contenido[i:i+20] for i in range(0, len(nuevo_contenido), 20)] if nuevo_contenido else []
        anterior = None
        primer = None
        for i, texto in enumerate(bloques):
            fin = (i == len(bloques) - 1)
            ruta_bloque = self._crear_bloque(texto, fin=fin)
            if anterior:
                bloque_prev = self._leer_bloque(anterior)
                bloque_prev["siguiente"] = ruta_bloque
                with open(anterior, "w", encoding="utf-8") as f:
                    json.dump(bloque_prev, f, indent=2, ensure_ascii=False)
            else:
                primer = ruta_bloque
            anterior = ruta_bloque

        entrada["ruta_datos"] = primer
        entrada["tamano"] = len(nuevo_contenido)
        entrada["fecha_modificacion"] = fecha_actual()
        self._guardar_tabla()

    def mover_a_papelera(self, entrada, usuario):
        if usuario != entrada["propietario"] and not self._permite_escritura(entrada, usuario):
            raise PermissionError("No puedes eliminar este archivo.")
        entrada["papelera"] = True
        entrada["fecha_eliminacion"] = fecha_actual()
        self._guardar_tabla()

    def recuperar_archivo(self, entrada, usuario):
        if usuario != entrada["propietario"] and usuario != "admin":
            raise PermissionError("Solo el propietario o admin pueden recuperar archivos.")
        entrada["papelera"] = False
        entrada["fecha_eliminacion"] = None
        entrada["fecha_modificacion"] = fecha_actual()
        self._guardar_tabla()

    def eliminar_permanente(self, entrada, usuario):
        if usuario != entrada["propietario"] and usuario != "admin":
            raise PermissionError("Solo el propietario o admin pueden borrar permanentemente.")
        self._eliminar_bloques(entrada["ruta_datos"])
        self.tabla = [e for e in self.tabla if e["id"] != entrada["id"]]
        self._guardar_tabla()

    def _eliminar_bloques(self, ruta_inicial):
        actual = ruta_inicial
        while actual:
            try:
                bloque = self._leer_bloque(actual)
            except FileNotFoundError:
                break
            siguiente = bloque.get("siguiente")
            try:
                os.remove(actual)
            except FileNotFoundError:
                pass
            actual = siguiente

    def cambiar_permisos(self, entrada, usuario_objetivo, lectura, escritura, usuario):
        if usuario != entrada["propietario"]:
            raise PermissionError("Solo el propietario puede modificar permisos.")
        entrada["permisos"][usuario_objetivo] = {
            "lectura": bool(lectura),
            "escritura": bool(escritura)
        }
        entrada["fecha_modificacion"] = fecha_actual()
        self._guardar_tabla()

    def _permite_lectura(self, entrada, usuario):
        permisos = entrada.get("permisos", {}).get(usuario)
        return permisos.get("lectura", False) if permisos else False

    def _permite_escritura(self, entrada, usuario):
        permisos = entrada.get("permisos", {}).get(usuario)
        return permisos.get("escritura", False) if permisos else False


# ---------- Interfaz gráfica ----------
class InterfazFAT:
    def __init__(self, raiz):
        self.raiz = raiz
        self.raiz.title("Proyecto FAT - Interfaz moderna")
        self.gestor = GestorFAT()
        self.usuarios = ["admin", "josh", "fatima", "invitado"]
        self.usuario_actual = tb.StringVar(value=self.usuarios[0])

        barra = tb.Frame(self.raiz, padding=10)
        barra.pack(fill=X)

        tb.Label(barra, text="Usuario:").pack(side=LEFT, padx=5)
        tb.OptionMenu(barra, self.usuario_actual, *self.usuarios).pack(side=LEFT)

        tb.Button(barra, text="Crear archivo", bootstyle="success", command=self.crear_archivo).pack(side=LEFT, padx=5)
        tb.Button(barra, text="Modificar", bootstyle="warning", command=self.modificar_archivo).pack(side=LEFT, padx=5)
        tb.Button(barra, text="Papelera", bootstyle="secondary", command=self.ver_papelera).pack(side=LEFT, padx=5)
        tb.Button(barra, text="Permisos", bootstyle="info", command=self.permisos_archivo).pack(side=LEFT, padx=5)
        tb.Button(barra, text="Refrescar", bootstyle="light", command=self.actualizar_lista).pack(side=RIGHT, padx=5)

        self.tabla = tb.Treeview(self.raiz, columns=("nombre", "tamano", "propietario", "fecha"), show="headings", height=14)
        self.tabla.heading("nombre", text="Nombre")
        self.tabla.heading("tamano", text="Tamaño")
        self.tabla.heading("propietario", text="Propietario")
        self.tabla.heading("fecha", text="Modificado")
        self.tabla.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.tabla.bind("<Double-1>", self.abrir_archivo)
        self.actualizar_lista()

    def actualizar_lista(self):
        for i in self.tabla.get_children():
            self.tabla.delete(i)
        for e in self.gestor.listar_archivos():
            self.tabla.insert("", "end", iid=e["id"],
                              values=(e["nombre"], e["tamano"], e["propietario"], e["fecha_modificacion"]))

    def _archivo_seleccionado(self):
        seleccion = self.tabla.selection()
        if seleccion:
            return self.gestor.obtener_entrada(seleccion[0])
        Messagebox.show_info("Atención", "Selecciona un archivo primero.")
        return None

    def crear_archivo(self):
        nombre = simpledialog.askstring("Nuevo archivo", "Nombre del archivo:")
        if not nombre:
            return
        contenido = simpledialog.askstring("Contenido", "Escribe el contenido inicial:")
        usuario = self.usuario_actual.get()
        try:
            self.gestor.crear_archivo(nombre, contenido or "", usuario)
            Messagebox.show_info("Éxito", "Archivo creado correctamente.")
            self.actualizar_lista()
        except Exception as e:
            Messagebox.show_error("Error", str(e))

    def abrir_archivo(self, _=None):
        entrada = self._archivo_seleccionado()
        if not entrada:
            return
        usuario = self.usuario_actual.get()
        try:
            contenido = self.gestor.leer_contenido(entrada, usuario)
            texto = (
                f"Nombre: {entrada['nombre']}\n"
                f"Propietario: {entrada['propietario']}\n"
                f"Tamaño: {entrada['tamano']} caracteres\n"
                f"Creado: {entrada['fecha_creacion']}\n"
                f"Modificado: {entrada['fecha_modificacion']}\n\n"
                f"--- Contenido ---\n{contenido}"
            )
            Messagebox.show_info(f"Abrir: {entrada['nombre']}", texto)
        except PermissionError as p:
            Messagebox.show_warning("Permiso denegado", str(p))

    def modificar_archivo(self):
        entrada = self._archivo_seleccionado()
        if not entrada:
            return
        usuario = self.usuario_actual.get()
        try:
            actual = self.gestor.leer_contenido(entrada, usuario)
        except PermissionError:
            actual = ""
        nuevo = simpledialog.askstring("Modificar", "Nuevo contenido:", initialvalue=actual)
        if nuevo is None:
            return
        try:
            self.gestor.modificar_archivo(entrada, nuevo, usuario)
            Messagebox.show_info("Listo", "Archivo modificado.")
            self.actualizar_lista()
        except PermissionError as p:
            Messagebox.show_warning("Permiso denegado", str(p))

    def ver_papelera(self):
        archivos = [a for a in self.gestor.listar_archivos(True) if a["papelera"]]
        if not archivos:
            Messagebox.show_info("Papelera", "Está vacía.")
            return

        texto = "Archivos en papelera:\n\n" + "\n".join(
            [f"- {a['nombre']} ({a['propietario']})" for a in archivos]
        )
        Messagebox.show_info("Papelera", texto)

        accion = simpledialog.askstring(
            "Papelera",
            "Escribe el nombre del archivo para recuperar o borrar permanentemente.\n"
            "Prefijo 'R:' para recuperar, 'B:' para borrar (ej: R:archivo.txt o B:archivo.txt)"
        )

        if not accion:
            return

        if accion.startswith("R:"):
            nombre = accion[2:].strip()
            for a in archivos:
                if a["nombre"] == nombre:
                    try:
                        self.gestor.recuperar_archivo(a, self.usuario_actual.get())
                        Messagebox.show_info("Recuperado", "Archivo restaurado.")
                        self.actualizar_lista()
                        return
                    except PermissionError as p:
                        Messagebox.show_warning("Permiso denegado", str(p))
                        return
            Messagebox.show_error("Error", "No se encontró ese archivo en la papelera.")

        elif accion.startswith("B:"):
            nombre = accion[2:].strip()
            for a in archivos:
                if a["nombre"] == nombre:
                    try:
                        self.gestor.eliminar_permanente(a, self.usuario_actual.get())
                        Messagebox.show_info("Borrado", "Archivo eliminado permanentemente.")
                        self.actualizar_lista()
                        return
                    except PermissionError as p:
                        Messagebox.show_warning("Permiso denegado", str(p))
                        return
            Messagebox.show_error("Error", "No se encontró ese archivo en la papelera.")


    def permisos_archivo(self):
        entrada = self._archivo_seleccionado()
        if not entrada:
            return
        usuario = self.usuario_actual.get()
        texto = "Permisos actuales:\n"
        for u, p in entrada["permisos"].items():
            texto += f"- {u}: lectura={p['lectura']} escritura={p['escritura']}\n"
        Messagebox.show_info("Permisos", texto)
        cambio = simpledialog.askstring("Modificar permisos", "Formato: usuario,lectura,escritura (ej: fatima,1,0)")
        if not cambio:
            return
        try:
            u, r, w = [x.strip() for x in cambio.split(",")]
            self.gestor.cambiar_permisos(entrada, u, int(r), int(w), usuario)
            Messagebox.show_info("Listo", "Permisos actualizados.")
        except PermissionError as p:
            Messagebox.show_warning("Permiso denegado", str(p))
        except Exception as e:
            Messagebox.show_error("Error", str(e))


app = tb.Window(themename="minty")
InterfazFAT(app)
app.mainloop()
