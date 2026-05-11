import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import random
from groq import Groq

# ─────────────────────────────────────────────────────────
# Colores del tema oscuro
# ─────────────────────────────────────────────────────────
BG         = "#121212"
BG_CARD    = "#1e1e1e"
BG_BUTTON  = "#2a2a2a"
ACCENT     = "#4f8ef7"
ACCENT_HOV = "#3a70d4"
SUCCESS    = "#2e7d32"
ERROR      = "#c62828"
TEXT       = "#e8e8e8"
SUBTEXT    = "#9e9e9e"
GEMINI_BG  = "#1a1a2e"

W, H = 1280, 720

def center_window(win, w, h):
    win.update_idletasks()
    x = (win.winfo_screenwidth() // 2) - (w // 2)
    y = (win.winfo_screenheight() // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")


# ─────────────────────────────────────────────────────────
# Ventana Principal
# ─────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestor de Preguntas Tipo Test")
        self.configure(bg=BG)
        center_window(self, W, H)
        self.resizable(False, False)

        self.questions = []

        # ── Título ──────────────────────────────────────
        tk.Label(
            self, text="Gestor de Preguntas", bg=BG, fg=TEXT,
            font=("Segoe UI", 28, "bold")
        ).pack(pady=(80, 5))

        tk.Label(
            self, text="Importa un archivo .txt con tus preguntas tipo test",
            bg=BG, fg=SUBTEXT, font=("Segoe UI", 12)
        ).pack(pady=(0, 40))

        # ── API Key ──────────────────────────────────────
        frame_key = tk.Frame(self, bg=BG)
        frame_key.pack(pady=(0, 20))

        tk.Label(
            frame_key, text="API Key de Groq:", bg=BG, fg=SUBTEXT,
            font=("Segoe UI", 11)
        ).pack(side="left", padx=(0, 10))

        self.api_key_var = tk.StringVar()
        self.api_entry = tk.Entry(
            frame_key, textvariable=self.api_key_var,
            font=("Segoe UI", 11), bg=BG_CARD, fg=TEXT,
            insertbackground=TEXT, relief="flat",
            width=45, show="•"
        )
        self.api_entry.pack(side="left", ipady=8, padx=5)

        # Toggle mostrar/ocultar key
        self.show_key = False
        self.toggle_btn = tk.Button(
            frame_key, text="👁", bg=BG_CARD, fg=SUBTEXT,
            font=("Segoe UI", 11), relief="flat", cursor="hand2",
            command=self.toggle_key_visibility
        )
        self.toggle_btn.pack(side="left", padx=4)

        # ── Botón importar ────────────────────────────────
        self.import_button = tk.Button(
            self, text="  📂  Importar preguntas tipo test  ",
            command=self.import_file,
            font=("Segoe UI", 13, "bold"),
            bg=ACCENT, fg="white",
            activebackground=ACCENT_HOV, activeforeground="white",
            relief="flat", padx=24, pady=14, cursor="hand2"
        )
        self.import_button.pack(pady=10)

        # ── Info formato ──────────────────────────────────
        info = (
            "Formato del archivo .txt\n\n"
            "Nombre de la pregunta\n"
            "Número de la respuesta correcta (1, 2, 3...)\n"
            "Respuesta 1\nRespuesta 2\n...\n\n"
            "(Separar cada pregunta con una línea en blanco)"
        )
        tk.Label(
            self, text=info, bg=BG_CARD, fg=SUBTEXT,
            font=("Segoe UI", 10), justify="left",
            wraplength=500, padx=20, pady=16
        ).pack(pady=30, ipadx=10)

    def toggle_key_visibility(self):
        self.show_key = not self.show_key
        self.api_entry.config(show="" if self.show_key else "•")

    def import_file(self):
        filepath = filedialog.askopenfilename(
            title="Selecciona el archivo de preguntas",
            filetypes=(("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*"))
        )
        if not filepath:
            return

        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("API Key", "Introduce tu API Key de Grok para continuar.")
            return

        self.questions = self.parse_questions(filepath)
        if not self.questions:
            messagebox.showerror("Error", "No se encontraron preguntas válidas o el formato es incorrecto.")
            return

        self.withdraw()
        TestWindow(self, self.questions, api_key)

    def parse_questions(self, filepath):
        parsed = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read().strip().replace('\r\n', '\n')

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
# Ventana del Test
# ─────────────────────────────────────────────────────────
class TestWindow(tk.Toplevel):
    def __init__(self, master, questions, api_key):
        super().__init__(master)
        self.title("Realizando Test")
        self.configure(bg=BG)
        center_window(self, W, H)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.questions   = list(questions)  # copia para no mutar el original
        random.shuffle(self.questions)        # orden aleatorio
        self.current_idx = 0
        self.api_key     = api_key
        self.answered    = False
        self.answer_buttons = []

        self._build_ui()
        self.load_question()

    # ── Layout ──────────────────────────────────────────
    def _build_ui(self):
        # Cabecera
        header = tk.Frame(self, bg=BG_CARD, height=55)
        header.pack(fill="x")
        header.pack_propagate(False)

        self.counter_label = tk.Label(
            header, text="", bg=BG_CARD, fg=SUBTEXT, font=("Segoe UI", 11)
        )
        self.counter_label.pack(side="left", padx=25, pady=15)

        tk.Button(
            header, text="✕ Salir", bg=BG_CARD, fg=SUBTEXT,
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            activebackground=BG_CARD, activeforeground=ERROR,
            command=self.on_close
        ).pack(side="right", padx=15, pady=10)

        # Cuerpo dividido: izquierda (pregunta) | derecha (Gemini)
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=0, pady=0)

        # ── Panel izquierdo ──────────────────────────────
        left = tk.Frame(body, bg=BG, width=700)
        left.pack(side="left", fill="both", expand=True, padx=40, pady=30)
        left.pack_propagate(False)

        self.q_label = tk.Label(
            left, text="", bg=BG, fg=TEXT,
            font=("Segoe UI", 17, "bold"),
            wraplength=600, justify="left", anchor="nw"
        )
        self.q_label.pack(fill="x", pady=(10, 24))

        self.buttons_frame = tk.Frame(left, bg=BG)
        self.buttons_frame.pack(fill="x")

        self.next_button = tk.Button(
            left, text="Siguiente →",
            command=self.next_question,
            font=("Segoe UI", 12, "bold"),
            bg=ACCENT, fg="white",
            activebackground=ACCENT_HOV, activeforeground="white",
            relief="flat", padx=22, pady=10, cursor="hand2",
            state=tk.DISABLED
        )
        self.next_button.pack(side="bottom", anchor="e", pady=10)

        # ── Separador vertical ────────────────────────────
        tk.Frame(body, bg="#2a2a2a", width=1).pack(side="left", fill="y")

        # ── Panel derecho (Gemini) ────────────────────────
        right = tk.Frame(body, bg=GEMINI_BG, width=480)
        right.pack(side="right", fill="both")
        right.pack_propagate(False)

        gem_header = tk.Frame(right, bg=GEMINI_BG)
        gem_header.pack(fill="x", padx=20, pady=(20, 10))

        tk.Label(
            gem_header, text="✦ Groq AI  (Llama 3.3)", bg=GEMINI_BG, fg=ACCENT,
            font=("Segoe UI", 13, "bold")
        ).pack(side="left")

        self.gemini_status = tk.Label(
            gem_header, text="", bg=GEMINI_BG, fg=SUBTEXT,
            font=("Segoe UI", 9)
        )
        self.gemini_status.pack(side="right")

        self.gemini_text = scrolledtext.ScrolledText(
            right, wrap=tk.WORD, bg=GEMINI_BG, fg=TEXT,
            font=("Segoe UI", 11), relief="flat",
            insertbackground=TEXT, state=tk.DISABLED,
            padx=16, pady=10
        )
        self.gemini_text.pack(fill="both", expand=True, padx=10, pady=(0, 20))

    # ── Cargar pregunta ──────────────────────────────────
    def load_question(self):
        for w in self.buttons_frame.winfo_children():
            w.destroy()

        self.answered = False
        q = self.questions[self.current_idx]
        self.counter_label.config(text=f"Pregunta  {self.current_idx + 1}  /  {len(self.questions)}")
        self.q_label.config(text=q['question'])

        # Limpiar panel Gemini
        self._set_gemini_text("Responde la pregunta para ver el análisis de Gemini.")
        self.gemini_status.config(text="")

        self.answer_buttons = []
        for i, ans in enumerate(q['answers']):
            btn = tk.Button(
                self.buttons_frame,
                text=f"  {chr(65+i)}.  {ans}",
                bg=BG_BUTTON, fg=TEXT,
                font=("Segoe UI", 12),
                relief="flat", anchor="w",
                padx=14, pady=10,
                activebackground="#3a3a3a", activeforeground="white",
                cursor="hand2",
                command=lambda idx=i: self.check_answer(idx)
            )
            btn.pack(fill="x", pady=4)
            self.answer_buttons.append(btn)

        self.next_button.config(
            state=tk.DISABLED, bg="#2a2a2a", fg="#666666", cursor="arrow"
        )

    # ── Comprobar respuesta ──────────────────────────────
    def check_answer(self, selected_idx):
        if self.answered:
            return

        self.answered = True
        q = self.questions[self.current_idx]
        correct_idx = q['correct_index']

        for i, btn in enumerate(self.answer_buttons):
            if i == correct_idx:
                btn.config(bg=SUCCESS, fg="white", disabledforeground="white")
            elif i == selected_idx:
                btn.config(bg=ERROR, fg="white", disabledforeground="white")
            btn.config(state=tk.DISABLED, cursor="arrow")

        # Habilitar siguiente / finalizar
        is_last = self.current_idx >= len(self.questions) - 1
        self.next_button.config(
            state=tk.NORMAL, bg=ACCENT, fg="white", cursor="hand2",
            text="Finalizar" if is_last else "Siguiente →"
        )

        # Llamar a Gemini en un hilo separado
        self.gemini_status.config(text="⏳ consultando...")
        self._set_gemini_text("")
        threading.Thread(
            target=self._ask_groq,
            args=(q,),
            daemon=True
        ).start()

    def _ask_groq(self, q):
        try:
            client = Groq(api_key=self.api_key)

            opciones = "\n".join(
                [f"  {'(CORRECTA)' if i == q['correct_index'] else chr(65+i)}. {ans}"
                 for i, ans in enumerate(q['answers'])]
            )
            prompt = (
                "Pregunta de tipo test:\n\n"
                + '"' + q['question'] + '"' + "\n\n"
                + "Opciones (la correcta esta marcada con (CORRECTA)):\n" + opciones + "\n\n"
                + "Responde brevemente en espanol: explica POR QUE la respuesta correcta es correcta "
                + "y, si aplica, por que las demas son incorrectas. Se claro y educativo."
            )

            chat = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512
            )
            result_text = chat.choices[0].message.content

        except Exception as e:
            result_text = f"Error al contactar con Groq:\n{str(e)}"

        self.after(0, lambda: self._on_gemini_response(result_text))

    def _on_gemini_response(self, text):
        self._set_gemini_text(text)
        self.gemini_status.config(text="✦ listo")

    def _set_gemini_text(self, text):
        self.gemini_text.config(state=tk.NORMAL)
        self.gemini_text.delete("1.0", tk.END)
        self.gemini_text.insert(tk.END, text)
        self.gemini_text.config(state=tk.DISABLED)

    # ── Siguiente pregunta ───────────────────────────────
    def next_question(self):
        if self.current_idx < len(self.questions) - 1:
            self.current_idx += 1
            self.load_question()
        else:
            messagebox.showinfo("¡Fin del test!", "Has completado todas las preguntas.", parent=self)
            self.on_close()

    def on_close(self):
        self.destroy()
        self.master.deiconify()


# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
