import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
import threading
import random
import os
import re
import io
import urllib.request
from groq import Groq, RateLimitError
from PIL import Image, ImageTk

# ─────────────────────────────────────────────────────────
# Configuración inicial
# ─────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG = "#121212"
BG_CARD = "#1e1e1e"
ACCENT = "#4f8ef7"
ACCENT_HOV = "#3a70d4"
SUCCESS = "#2e7d32"
ERROR = "#c62828"
TEXT = "#e8e8e8"
SUBTEXT = "#9e9e9e"
GROQ_BG = "#1a1a2e"

W, H = 1280, 720


# ─────────────────────────────────────────────────────────
# Markdown renderer para widgets Text de tkinter
# ─────────────────────────────────────────────────────────
def apply_markdown_tags(text_widget, font_size=15):
    """Configura los tags de Markdown sobre un widget tk.Text."""
    bold_font   = ("Segoe UI", font_size, "bold")
    italic_font = ("Segoe UI", font_size, "italic")
    bi_font     = ("Segoe UI", font_size, "bold italic")
    h1_font     = ("Segoe UI", font_size + 8, "bold")
    h2_font     = ("Segoe UI", font_size + 4, "bold")
    h3_font     = ("Segoe UI", font_size + 2, "bold")
    code_font   = ("Consolas", font_size)
    code_bg     = "#1e1e2e"
    code_fg     = "#a6e3a1"

    text_widget.tag_configure("h1",     font=h1_font,   foreground=TEXT)
    text_widget.tag_configure("h2",     font=h2_font,   foreground=TEXT)
    text_widget.tag_configure("h3",     font=h3_font,   foreground=TEXT)
    text_widget.tag_configure("bold",   font=bold_font,  foreground=TEXT)
    text_widget.tag_configure("italic", font=italic_font, foreground=TEXT)
    text_widget.tag_configure("bi",     font=bi_font,   foreground=TEXT)
    text_widget.tag_configure("code",   font=code_font,  background=code_bg, foreground=code_fg)
    text_widget.tag_configure("codeblock", font=code_font, background=code_bg,
                              foreground=code_fg, lmargin1=10, lmargin2=10, spacing1=4, spacing3=4)
    text_widget.tag_configure("normal", font=("Segoe UI", font_size), foreground=TEXT)


def render_markdown(text_widget, raw_text):
    """
    Inserta 'raw_text' en un widget tk.Text con formato Markdown básico.
    Soporta: # h1/h2/h3, **bold**, *italic*, ***bold italic***, `code`, bloques ```code```.
    Requiere haber llamado antes a apply_markdown_tags().
    """
    text_widget.configure(state="normal")
    text_widget.delete("1.0", "end")

    # Separar primero los bloques de código ``` ... ```
    segments = re.split(r'(```[\s\S]*?```)', raw_text)

    for seg in segments:
        if seg.startswith('```') and seg.endswith('```'):
            # Bloque de código
            inner = seg[3:-3].lstrip('\n')
            # Eliminar posible lenguaje en la primera línea (```python ...)
            inner = re.sub(r'^[a-zA-Z]*\n', '', inner)
            text_widget.insert("end", inner + "\n", "codeblock")
        else:
            # Procesar línea a línea para encabezados
            lines = seg.split('\n')
            for li, line in enumerate(lines):
                if li > 0:
                    text_widget.insert("end", "\n")

                h_match = re.match(r'^(#{1,3})\s+(.*)', line)
                if h_match:
                    level = len(h_match.group(1))
                    content = h_match.group(2)
                    tag = f"h{level}"
                    _insert_inline(text_widget, content, base_tag=tag)
                else:
                    _insert_inline(text_widget, line, base_tag="normal")

    text_widget.configure(state="disabled")


_INLINE_RE = re.compile(
    r'(\*\*\*(.+?)\*\*\*)'   # bold+italic
    r'|(\*\*(.+?)\*\*)'       # bold
    r'|(\*(.+?)\*)'           # italic
    r'|(__(.+?)__)'           # bold (alt)
    r'|(_(.+?)_)'             # italic (alt)
    r'|(`(.+?)`)',             # inline code
    re.DOTALL
)


def _resolve_inline_tag(match, base_tag):
    """Devuelve (text, tag) para un match de _INLINE_RE."""
    if match.group(1):   return match.group(2), "bi"
    if match.group(3):   return match.group(4), "bold"
    if match.group(5):   return match.group(6), "italic"
    if match.group(7):   return match.group(8), "bold"
    if match.group(9):   return match.group(10), "italic"
    if match.group(11):  return match.group(12), "code"
    return match.group(0), base_tag


def _insert_inline(text_widget, line, base_tag="normal"):
    """Inserta una línea de texto procesando los tokens inline de Markdown."""
    last = 0
    for m in _INLINE_RE.finditer(line):
        start, end = m.span()
        if start > last:
            text_widget.insert("end", line[last:start], base_tag)
        content, tag = _resolve_inline_tag(m, base_tag)
        text_widget.insert("end", content, tag)
        last = end
    if last < len(line):
        text_widget.insert("end", line[last:], base_tag)


# URL de imagen en markdown: soporta http/https, termina en png/jpg/jpeg/gif/webp
_IMG_URL_RE = re.compile(
    r'https?://\S+\.(?:png|jpg|jpeg|gif|webp)(?:[^\s\)\]]*)?',
    re.IGNORECASE
)


# ─────────────────────────────────────────────────────────
# Widget: pregunta con Markdown + soporte de imagen
# ─────────────────────────────────────────────────────────
class MarkdownTextbox(ctk.CTkFrame):
    """CTkFrame con un tk.Text para texto Markdown y una imagen opcional debajo.
    Usa grid internamente: fila 0 = texto (se expande), fila 1 = imagen (fija).
    """
    _BG_RGB = tuple(int(BG.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

    def __init__(self, master, font_size=22, fg_color="transparent", **kw):
        super().__init__(master, fg_color=fg_color, **kw)
        self._font_size = font_size
        self._img_ref   = None

        # Grid: fila 0 = texto (peso 1), fila 1 = imagen (peso 0)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self._txt = tk.Text(
            self, wrap="word", bd=0, highlightthickness=0,
            background=BG, foreground=TEXT,
            insertbackground=BG, selectbackground=ACCENT,
            font=("Segoe UI", font_size),
            cursor="arrow",
            spacing1=4, spacing3=2,
        )
        self._txt.grid(row=0, column=0, sticky="nsew")
        apply_markdown_tags(self._txt, font_size)
        self._txt.configure(state="disabled")

        # Fila 1: contenedor de imagen (no visible hasta que haya una)
        self._img_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._img_label = tk.Label(self._img_frame, bg=BG, cursor="arrow")
        self._img_label.pack()
        self._loading_label = ctk.CTkLabel(
            self._img_frame,
            text="⏳ Cargando imagen...",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="gray"
        )

    def set_markdown(self, text):
        # Detectar y extraer URLs de imagen del texto
        img_urls = _IMG_URL_RE.findall(text)
        clean_text = _IMG_URL_RE.sub('', text).strip()

        render_markdown(self._txt, clean_text)

        # Ocultar imagen anterior
        self._img_frame.grid_forget()
        self._loading_label.pack_forget()
        self._img_label.configure(image='')
        self._img_ref = None

        if img_urls:
            self._img_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
            self._loading_label.pack(pady=4)
            threading.Thread(
                target=self._load_image,
                args=(img_urls[0],),
                daemon=True
            ).start()

    def _load_image(self, url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            img = Image.open(io.BytesIO(data))

            # Componer canal alfa sobre el fondo oscuro para evitar imagen negra
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                background = Image.new("RGBA", img.size, self._BG_RGB + (255,))
                background.paste(img, mask=img.split()[3])
                img = background.convert("RGB")
            else:
                img = img.convert("RGB")

            img.thumbnail((700, 320), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.after(0, lambda: self._show_image(photo))
        except Exception as exc:
            self.after(0, lambda: self._show_error(str(exc)))

    def _show_image(self, photo):
        self._img_ref = photo
        self._loading_label.pack_forget()
        self._img_label.configure(image=photo)
        self._img_label.pack(pady=(4, 8))

    def _show_error(self, msg):
        self._loading_label.configure(text="⚠️ No se pudo cargar la imagen", text_color="#c62828")

# ─────────────────────────────────────────────────────────
# Widget: botón de respuesta con Markdown
# ─────────────────────────────────────────────────────────
class MarkdownButton(ctk.CTkFrame):
    """Botón con texto Markdown. Simula hover y estados de color."""

    # colores base
    _NORMAL_BG  = "#2a2a2a"
    _HOVER_BG   = "#3a3a3a"
    _ACTIVE_BG  = None  # se fija en set_state()

    def __init__(self, master, letter, answer_text, command, font_size=15, **kw):
        super().__init__(master, fg_color=self._NORMAL_BG, corner_radius=8, **kw)
        self._cmd      = command
        self._enabled  = True
        self._bg_color = self._NORMAL_BG
        self._font_size = font_size

        prefix = f"{letter}.  "

        self._txt = tk.Text(
            self, wrap="word", bd=0, highlightthickness=0,
            background=self._NORMAL_BG, foreground=TEXT,
            insertbackground=self._NORMAL_BG,
            font=("Segoe UI", font_size),
            cursor="hand2",
            spacing1=3, spacing3=3,
            padx=14, pady=12,
            height=1,        # empieza en 1 línea; se autoajusta tras el primer Configure
        )
        self._txt.pack(fill="x")   # sin expand, así no fagocita el alto
        apply_markdown_tags(self._txt, font_size)

        # Insertar letra en bold y luego el contenido md
        self._txt.configure(state="normal")
        self._txt.insert("end", prefix, "bold")
        _insert_inline(self._txt, answer_text, base_tag="normal")
        self._txt.configure(state="disabled")

        # Bind eventos
        for w in (self, self._txt):
            w.bind("<Enter>",   self._on_enter)
            w.bind("<Leave>",   self._on_leave)
            w.bind("<Button-1>", self._on_click)

        # Auto-ajustar altura cuando el widget tenga un ancho válido
        self._txt.bind("<Configure>", self._auto_height)

    # --------------------------------------------------
    def _auto_height(self, event=None):
        """Reajusta la altura del Text al número real de líneas visuales."""
        try:
            lines = self._txt.count("1.0", "end", "displaylines")
            if lines:
                self._txt.configure(height=max(1, lines[0]))
        except Exception:
            pass

    def _set_bg(self, color):
        self._bg_color = color
        self.configure(fg_color=color)
        self._txt.configure(background=color)

    def _on_enter(self, _=None):
        if self._enabled:
            self._set_bg(self._HOVER_BG)

    def _on_leave(self, _=None):
        if self._enabled:
            self._set_bg(self._NORMAL_BG)

    def _on_click(self, _=None):
        if self._enabled and self._cmd:
            self._cmd()

    def set_state(self, color=None):
        """
        Deshabilita el botón y opcionalmente lo colorea.
        color: None = gris apagado, SUCCESS = verde, ERROR = rojo.
        """
        self._enabled = False
        self._txt.configure(cursor="arrow")
        if color:
            self._set_bg(color)
            self._txt.configure(foreground="white")
            for tag in ("bold", "italic", "bi", "h1", "h2", "h3", "normal", "code", "codeblock"):
                self._txt.tag_configure(tag, foreground="white")
        else:
            self._set_bg("#222222")
            self._txt.configure(foreground=SUBTEXT)
            for tag in ("bold", "italic", "bi", "h1", "h2", "h3", "normal"):
                self._txt.tag_configure(tag, foreground=SUBTEXT)

def center_window(win, w, h):
    win.update_idletasks()
    x = (win.winfo_screenwidth() // 2) - (w // 2)
    y = (win.winfo_screenheight() // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")

# ─────────────────────────────────────────────────────────
# Ventana Principal
# ─────────────────────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gestor de Preguntas Tipo Test")
        self.geometry(f"{W}x{H}")
        self.minsize(1024, 600)
        center_window(self, W, H)
        self.resizable(True, True)

        self.questions = []

        # Contenedor central para centrar verticalmente
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(expand=True)

        # ── Título ──────────────────────────────────────
        ctk.CTkLabel(
            main_frame, text="Gestor de Preguntas", 
            font=ctk.CTkFont(family="Segoe UI", size=32, weight="bold")
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            main_frame, text="Importa una carpeta con archivos .txt de preguntas tipo test",
            font=ctk.CTkFont(family="Segoe UI", size=14), text_color="gray"
        ).pack(pady=(0, 40))

        # ── API Key ──────────────────────────────────────
        frame_key = ctk.CTkFrame(main_frame, fg_color="transparent")
        frame_key.pack(pady=(0, 20))

        ctk.CTkLabel(
            frame_key, text="API Key de Groq:", 
            font=ctk.CTkFont(family="Segoe UI", size=13)
        ).pack(side="left", padx=(0, 10))

        self.api_key_var = ctk.StringVar()
        self.api_entry = ctk.CTkEntry(
            frame_key, textvariable=self.api_key_var,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            width=350, height=40, show="•"
        )
        self.api_entry.pack(side="left", padx=5)

        self.show_key = False
        self.toggle_btn = ctk.CTkButton(
            frame_key, text="👁", width=40, height=40,
            fg_color="#333333", hover_color="#444444",
            command=self.toggle_key_visibility
        )
        self.toggle_btn.pack(side="left", padx=5)

        # ── Botón importar ────────────────────────────────
        self.import_button = ctk.CTkButton(
            main_frame, text="📂 Importar carpeta de preguntas",
            command=self.import_file,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOV,
            height=50, width=300
        )
        self.import_button.pack(pady=20)

        # ── Info formato ──────────────────────────────────
        info = (
            "Formato de los archivos .txt en la carpeta\n\n"
            "Nombre de la pregunta\n"
            "Número de la respuesta correcta (1, 2, 3...)\n"
            "Respuesta 1\nRespuesta 2\n...\n\n"
            "(Separar cada pregunta con una línea en blanco)"
        )
        info_frame = ctk.CTkFrame(main_frame, fg_color=BG_CARD, corner_radius=10)
        info_frame.pack(pady=30)
        
        ctk.CTkLabel(
            info_frame, text=info, justify="left",
            font=ctk.CTkFont(family="Segoe UI", size=13), text_color="gray"
        ).pack(padx=30, pady=20)

    def toggle_key_visibility(self):
        self.show_key = not self.show_key
        self.api_entry.configure(show="" if self.show_key else "•")

    def import_file(self):
        folderpath = filedialog.askdirectory(
            title="Selecciona la carpeta con archivos de preguntas"
        )
        if not folderpath:
            return

        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("API Key", "Introduce tu API Key de Grok para continuar.")
            return

        file_data = []
        for filename in os.listdir(folderpath):
            if filename.lower().endswith(".txt"):
                filepath = os.path.join(folderpath, filename)
                parsed = self.parse_questions(filepath)
                if parsed:
                    file_data.append({
                        'filename': filename,
                        'filepath': filepath,
                        'questions': parsed
                    })

        if not file_data:
            messagebox.showerror("Error", "No se encontraron preguntas válidas en los archivos .txt de la carpeta.")
            return

        self.withdraw()
        FileSelectionWindow(self, file_data, api_key)

    def parse_questions(self, filepath):
        parsed = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read().strip().replace('\r\n', '\n')

            # Convertir \n literal (dos chars: \ + n) a salto de línea real
            # para soportar tablas y texto multilínea compactado en una sola línea
            content = content.replace('\\n', '\n')

            blocks = content.split('\n\n')
            for block in blocks:
                lines = [l.strip() for l in block.split('\n') if l.strip()]
                if len(lines) >= 3:
                    try:
                        correct_idx = int(lines[1]) - 1
                    except ValueError:
                        continue
                    answers = lines[2:]
                    if 0 <= correct_idx < len(answers):
                        parsed.append({
                            'question': lines[0],
                            'correct_index': correct_idx,
                            'answers': answers
                        })
        except Exception as e:
            messagebox.showerror("Error al leer archivo", str(e))
        return parsed


# ─────────────────────────────────────────────────────────
# Ventana de Selección de Archivos
# ─────────────────────────────────────────────────────────
class FileSelectionWindow(ctk.CTkToplevel):
    def __init__(self, master, file_data, api_key):
        super().__init__(master)
        self.title("Seleccionar Archivos")
        self.geometry("700x550")
        center_window(self, 700, 550)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.file_data = file_data
        self.api_key = api_key
        self.checkboxes = []

        # Barra superior
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=30, pady=(25, 10))

        ctk.CTkLabel(
            top_frame, text="Selecciona los archivos", 
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        ).pack(side="left")

        ctk.CTkButton(
            top_frame, text="Desmarcar todos", command=self.deselect_all,
            font=ctk.CTkFont(family="Segoe UI", size=12), fg_color="#333", hover_color="#444", width=120
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            top_frame, text="Marcar todos", command=self.select_all,
            font=ctk.CTkFont(family="Segoe UI", size=12), fg_color="#333", hover_color="#444", width=120
        ).pack(side="right", padx=5)

        # Contenedor con scroll de CustomTkinter
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color=BG_CARD, corner_radius=10)
        self.scroll_frame.pack(fill="both", expand=True, padx=30, pady=10)

        # Crear filas usando CheckBox de CTk
        for data in self.file_data:
            row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#2a2a2a", corner_radius=8)
            row_frame.pack(fill="x", pady=5)
            
            var = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(
                row_frame, text=data['filename'], variable=var,
                font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                fg_color=ACCENT, hover_color=ACCENT_HOV
            )
            chk.pack(side="left", padx=15, pady=15)
            
            ctk.CTkLabel(
                row_frame, text=f"{len(data['questions'])} preguntas",
                font=ctk.CTkFont(family="Segoe UI", size=13), text_color="gray"
            ).pack(side="right", padx=15, pady=15)
            
            self.checkboxes.append((var, data))

        # Barra inferior
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=20)

        ctk.CTkButton(
            btn_frame, text="Volver", command=self.go_back,
            font=ctk.CTkFont(family="Segoe UI", size=14), fg_color="#333", hover_color="#444", width=120, height=40
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Continuar →", command=self.continue_test,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), fg_color=ACCENT, hover_color=ACCENT_HOV, width=150, height=40
        ).pack(side="right")

    def select_all(self):
        for var, _ in self.checkboxes:
            var.set(True)

    def deselect_all(self):
        for var, _ in self.checkboxes:
            var.set(False)

    def continue_test(self):
        combined_questions = []
        for var, data in self.checkboxes:
            if var.get():
                combined_questions.extend(data['questions'])

        if not combined_questions:
            messagebox.showwarning("Selección", "Por favor, selecciona al menos un archivo que contenga preguntas.")
            return

        self.withdraw()
        TestWindow(self, combined_questions, self.api_key)

    def go_back(self):
        self.destroy()
        self.master.deiconify()

    def on_close(self):
        self.master.destroy()


# ─────────────────────────────────────────────────────────
# Ventana del Test
# ─────────────────────────────────────────────────────────
class TestWindow(ctk.CTkToplevel):
    def __init__(self, master, questions, api_key):
        super().__init__(master)
        self.title("Realizando Test")
        self.geometry(f"{W}x{H}")
        self.minsize(1024, 600)
        center_window(self, W, H)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Deduplicar por texto de pregunta (preserva el primero encontrado)
        seen = set()
        unique = []
        for q in questions:
            key = q['question'].strip().lower()
            if key not in seen:
                seen.add(key)
                unique.append(q)
        self.questions = unique
        random.shuffle(self.questions)

        self.current_idx = 0
        self.api_key     = api_key
        self.answered    = False
        self.answer_buttons = []
        
        self.correct_count = 0
        self.incorrect_count = 0
        
        self.prompt_template = (
            "Actúa como un profesor experto y explica la siguiente pregunta de tipo test.\n\n"
            "PREGUNTA:\n\"{question}\"\n\n"
            "OPCIONES:\n{opciones}\n\n"
            "Tu tarea es explicar la respuesta de forma clara y concisa usando EXACTAMENTE el siguiente formato (no añadas saludos, ni introducciones, ni repitas 'La respuesta correcta es...'):\n\n"
            "✅ RESPUESTA CORRECTA\n"
            "[Indica solo la letra y el concepto de la respuesta correcta de forma directa]\n\n"
            "📖 CONTEXTO\n"
            "[Explica el porqué de la respuesta correcta y el concepto teórico subyacente de forma educativa]\n\n"
            "❌ OPCIONES INCORRECTAS\n"
            "[Explica brevemente por qué las otras opciones no son válidas, usando viñetas para cada una]"
        )

        self._build_ui()
        self.load_question()

    def _build_ui(self):
        # Cabecera
        header = ctk.CTkFrame(self, fg_color=BG_CARD, height=60, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        self.counter_label = ctk.CTkLabel(
            header, text="", font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        )
        self.counter_label.pack(side="left", padx=25, pady=15)

        self.progress = ctk.CTkProgressBar(header, width=150, fg_color="#333", progress_color=ACCENT)
        self.progress.pack(side="left", padx=20, pady=20)

        self.score_label = ctk.CTkLabel(
            header, text="Acierto: --%", font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=ACCENT
        )
        self.score_label.pack(side="left", padx=(10, 20), pady=15)

        self.penalty_var = ctk.StringVar(value="0 (No resta)")
        self.penalty_menu = ctk.CTkOptionMenu(
            header, variable=self.penalty_var,
            values=["0 (No resta)", "1/3 (3 mal = 1 bien)", "1/2 (2 mal = 1 bien)", "1/1 (1 mal = 1 bien)"],
            command=self.update_score, width=170, fg_color="#333", button_color="#444", button_hover_color="#555"
        )
        self.penalty_menu.pack(side="left", padx=5, pady=15)

        ctk.CTkButton(
            header, text="✕ Salir", width=80, height=30,
            fg_color="#333", hover_color=ERROR,
            command=self.go_back
        ).pack(side="right", padx=15, pady=15)

        # Cuerpo dividido
        self.left_weight = 70
        self.right_weight = 30
        
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)
        self.body.grid_columnconfigure(0, weight=self.left_weight, uniform="a")
        self.body.grid_columnconfigure(1, weight=0)
        self.body.grid_columnconfigure(2, weight=self.right_weight, uniform="a")
        self.body.grid_rowconfigure(0, weight=1)

        # Panel izquierdo — layout: next_button y buttons anclados abajo, q_box rellena el resto
        left = ctk.CTkFrame(self.body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=40, pady=30)

        # Botón siguiente — se empaqueta PRIMERO con side=bottom (queda abajo del todo)
        self.next_button = ctk.CTkButton(
            left, text="Siguiente →", command=self.next_question,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOV, height=45, width=150,
            state="disabled"
        )
        self.next_button.pack(side="bottom", anchor="e", pady=10)

        # Respuestas — justo encima del botón siguiente
        self.buttons_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.buttons_frame.pack(side="bottom", fill="x", pady=(0, 6))

        # Pregunta — ocupa el espacio restante en la parte superior
        self.q_box = MarkdownTextbox(left, font_size=22, fg_color="transparent")
        self.q_box.pack(fill="both", expand=True, pady=(10, 12))

        # Separador
        ctk.CTkFrame(self.body, width=2, fg_color="#2a2a2a").grid(row=0, column=1, sticky="ns")

        # Panel derecho
        right = ctk.CTkFrame(self.body, fg_color=GROQ_BG, corner_radius=0)
        right.grid(row=0, column=2, sticky="nsew")

        gem_header = ctk.CTkFrame(right, fg_color="transparent")
        gem_header.pack(fill="x", padx=20, pady=(25, 10))

        ctk.CTkLabel(
            gem_header, text="✦ Groq AI  (Llama 3.3)", text_color=ACCENT,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")
        ).pack(side="left")

        prompt_btn = ctk.CTkButton(
            gem_header, text="⚙️ Prompt", width=30, height=30,
            command=self._edit_prompt, fg_color="#333", hover_color="#444"
        )
        prompt_btn.pack(side="right", padx=(10, 0))

        self.groq_status = ctk.CTkLabel(
            gem_header, text="", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="gray"
        )
        self.groq_status.pack(side="right")

        self.groq_text = ctk.CTkTextbox(
            right, font=ctk.CTkFont(family="Segoe UI", size=17),
            fg_color="transparent", text_color=TEXT, wrap="word"
        )
        self.groq_text.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self.groq_button = ctk.CTkButton(
            right, text="✨ Consultar respuesta con Groq",
            command=self._on_groq_button_click,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="#4f8ef7", hover_color="#3a70d4",
            height=40, state="disabled"
        )
        self.groq_button.pack(fill="x", padx=20, pady=(0, 20))

    def load_question(self):
        if hasattr(self, 'left_weight') and self.left_weight != 70:
            self.animate_layout(70, 30)

        for w in self.buttons_frame.winfo_children():
            w.destroy()

        self.answered = False
        q = self.questions[self.current_idx]
        
        # Progreso
        prog_val = (self.current_idx) / len(self.questions)
        self.progress.set(prog_val)
        self.counter_label.configure(text=f"Pregunta  {self.current_idx + 1} / {len(self.questions)}")
        self.q_box.set_markdown(q['question'])

        self._set_groq_text("Responde la pregunta y luego presiona \"Consultar con Groq\" para ver el análisis.")
        self.groq_status.configure(text="")
        self.groq_button.configure(state="disabled")

        self.answer_buttons = []
        for i, ans in enumerate(q['answers']):
            btn = MarkdownButton(
                self.buttons_frame,
                letter=chr(65 + i),
                answer_text=ans,
                command=lambda idx=i: self.check_answer(idx),
                font_size=15,
            )
            btn.pack(fill="x", pady=6)
            self.answer_buttons.append(btn)

        self.next_button.configure(state="disabled", fg_color="#333", text_color="#777")

    def check_answer(self, selected_idx):
        if self.answered:
            return

        self.answered = True
        
        # Animación de paneles para darle más espacio a Groq, pero sin aplastar las preguntas
        self.animate_layout(50, 50)
        q = self.questions[self.current_idx]
        correct_idx = q['correct_index']

        if selected_idx == correct_idx:
            self.correct_count += 1
        else:
            self.incorrect_count += 1
            
        self.update_score()

        # Actualiza progreso actual tras responder
        self.progress.set((self.current_idx + 1) / len(self.questions))

        for i, btn in enumerate(self.answer_buttons):
            if i == correct_idx:
                btn.set_state(color=SUCCESS)
            elif i == selected_idx:
                btn.set_state(color=ERROR)
            else:
                btn.set_state(color=None)

        is_last = self.current_idx >= len(self.questions) - 1
        self.next_button.configure(
            state="normal", fg_color=ACCENT, text_color="white",
            text="Finalizar" if is_last else "Siguiente →"
        )

        self.groq_button.configure(state="normal")
        self.groq_status.configure(text="Listo para consultar")
        self._set_groq_text("Presiona \"Consultar con Groq\" para obtener el análisis de la IA.")

    def _on_groq_button_click(self):
        self.groq_button.configure(state="disabled")
        self.groq_status.configure(text="⏳ consultando...")
        self._set_groq_text("")
        q = self.questions[self.current_idx]
        threading.Thread(target=self._ask_groq, args=(q,), daemon=True).start()

    def _ask_groq(self, q):
        try:
            client = Groq(api_key=self.api_key)

            opciones = "\n".join(
                [f"  {chr(65+i)}. {ans}" + (" (CORRECTA)" if i == q['correct_index'] else "")
                 for i, ans in enumerate(q['answers'])]
            )
            try:
                prompt = self.prompt_template.format(
                    question=q['question'],
                    opciones=opciones
                )
            except Exception:
                prompt = self.prompt_template + f"\n\nPREGUNTA:\n{q['question']}\n\nOPCIONES:\n{opciones}"

            chat = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512
            )
            result_text = chat.choices[0].message.content
            result_text = result_text.replace('\\n', '\n')
            self.after(0, lambda: self._on_groq_response(result_text))

        except RateLimitError:
            self.after(0, lambda: self._show_quota_dialog(q))

        except Exception as e:
            result_text = f"Error al contactar con Groq:\n{str(e)}"
            self.after(0, lambda: self._on_groq_response(result_text))

    def _on_groq_response(self, text):
        self._set_groq_text(text)
        self.groq_status.configure(text="✦ listo")

    def _set_groq_text(self, text):
        self.groq_text.configure(state="normal")
        self.groq_text.delete("1.0", "end")
        self.groq_text.insert("end", text)
        self.groq_text.configure(state="disabled")

    def _show_quota_dialog(self, q):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Límite de API alcanzado")
        dialog.geometry("500x250")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        center_x = self.winfo_x() + (self.winfo_width() // 2) - 250
        center_y = self.winfo_y() + (self.winfo_height() // 2) - 125
        dialog.geometry(f"+{center_x}+{center_y}")

        ctk.CTkLabel(
            dialog,
            text="⚠️ Has agotado los tokens de tu API key de Groq.",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#ff6b6b"
        ).pack(pady=(25, 5))

        ctk.CTkLabel(
            dialog,
            text="Introduce una nueva API key para continuar:",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="gray"
        ).pack(pady=(0, 15))

        key_var = ctk.StringVar()
        entry = ctk.CTkEntry(
            dialog, textvariable=key_var,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            width=380, height=40, show="•"
        )
        entry.pack(pady=(0, 20))
        entry.focus_set()

        def _cancel():
            dialog.destroy()
            self.groq_button.configure(state="normal")
            self.groq_status.configure(text="Intenta de nuevo cuando tengas una nueva API key")

        dialog.protocol("WM_DELETE_WINDOW", _cancel)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack()

        ctk.CTkButton(
            btn_frame, text="Cancelar", width=120, height=35,
            fg_color="#444", hover_color="#555",
            command=_cancel
        ).pack(side="left", padx=10)

        def on_submit():
            new_key = key_var.get().strip()
            if not new_key:
                messagebox.showwarning("API Key", "La API key no puede estar vacía.", parent=dialog)
                return
            self.api_key = new_key
            dialog.destroy()
            self.groq_status.configure(text="⏳ reintentando...")
            self._set_groq_text("Reintentando con la nueva API key...")
            threading.Thread(target=self._ask_groq, args=(q,), daemon=True).start()

        ctk.CTkButton(
            btn_frame, text="Cambiar API Key", width=160, height=35,
            fg_color="#4f8ef7", hover_color="#3a70d4",
            command=on_submit
        ).pack(side="left", padx=10)

    def _edit_prompt(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Personalizar Prompt")
        dialog.geometry("700x500")
        dialog.transient(self)
        dialog.grab_set()
        center_window(dialog, 700, 500)

        ctk.CTkLabel(
            dialog, text="Edita el prompt del sistema.\nUsa {question} y {opciones} donde quieras que se inserten los datos.",
            font=ctk.CTkFont(family="Segoe UI", size=14), justify="left"
        ).pack(pady=(20, 10), padx=20, anchor="w")

        textbox = ctk.CTkTextbox(dialog, font=ctk.CTkFont(family="Segoe UI", size=13), wrap="word")
        textbox.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        textbox.insert("1.0", self.prompt_template)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(0, 20))

        def on_save():
            self.prompt_template = textbox.get("1.0", "end-1c")
            dialog.destroy()

        ctk.CTkButton(
            btn_frame, text="Cancelar", command=dialog.destroy,
            fg_color="#444", hover_color="#555", width=120
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame, text="Guardar", command=on_save,
            fg_color="#4f8ef7", hover_color="#3a70d4", width=120
        ).pack(side="left", padx=10)

    def next_question(self):
        if self.current_idx < len(self.questions) - 1:
            self.current_idx += 1
            self.load_question()
        else:
            messagebox.showinfo("¡Fin del test!", "Has completado todas las preguntas.", parent=self)
            self.on_close()

    def update_score(self, _=None):
        answered_total = self.correct_count + self.incorrect_count
        if answered_total == 0:
            self.score_label.configure(text="Acierto: --%")
            return
            
        mode = self.penalty_var.get()
        penalty = 0.0
        if "1/3" in mode:
            penalty = 1.0 / 3.0
        elif "1/2" in mode:
            penalty = 0.5
        elif "1/1" in mode:
            penalty = 1.0
            
        points = self.correct_count - (self.incorrect_count * penalty)
        points = max(0, points) # Limitar a 0 como mínimo
        
        percentage = (points / answered_total) * 100
        self.score_label.configure(text=f"Acierto: {percentage:.1f}%")

    def animate_layout(self, target_left, target_right):
        current_left = self.left_weight
        current_right = self.right_weight
        
        if current_left == target_left and current_right == target_right:
            return
            
        step_left = -2 if current_left > target_left else (2 if current_left < target_left else 0)
        step_right = -2 if current_right > target_right else (2 if current_right < target_right else 0)
        
        next_left = current_left + step_left
        next_right = current_right + step_right
        
        if (step_left < 0 and next_left <= target_left) or (step_left > 0 and next_left >= target_left):
            next_left = target_left
            next_right = target_right
            
        self.left_weight = next_left
        self.right_weight = next_right
        
        self.body.grid_columnconfigure(0, weight=self.left_weight, uniform="a")
        self.body.grid_columnconfigure(2, weight=self.right_weight, uniform="a")
        
        if next_left != target_left or next_right != target_right:
            self.after(10, lambda: self.animate_layout(target_left, target_right))

    def go_back(self):
        self.destroy()
        self.master.deiconify()

    def on_close(self):
        self.master.master.destroy()


# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
