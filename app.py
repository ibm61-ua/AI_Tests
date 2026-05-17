import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import random
import os
import textwrap
from groq import Groq

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
        center_window(self, W, H)
        self.resizable(False, False)

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
        center_window(self, W, H)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.questions   = list(questions)  
        random.shuffle(self.questions)       
        self.current_idx = 0
        self.api_key     = api_key
        self.answered    = False
        self.answer_buttons = []
        
        self.correct_count = 0
        self.incorrect_count = 0

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

        # Panel izquierdo
        left = ctk.CTkFrame(self.body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=40, pady=30)

        self.q_label = ctk.CTkLabel(
            left, text="", font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            justify="left", wraplength=800
        )
        self.q_label.pack(fill="x", pady=(10, 30), anchor="nw")
        
        def _update_wrap(event):
            # Dejamos un pequeño margen para que no toque los bordes exactamente
            wrap = max(200, event.width - 20)
            self.q_label.configure(wraplength=wrap)
        left.bind("<Configure>", _update_wrap)

        self.buttons_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.buttons_frame.pack(fill="x")

        self.next_button = ctk.CTkButton(
            left, text="Siguiente →", command=self.next_question,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOV, height=45, width=150,
            state="disabled"
        )
        self.next_button.pack(side="bottom", anchor="e", pady=10)

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

        self.groq_status = ctk.CTkLabel(
            gem_header, text="", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="gray"
        )
        self.groq_status.pack(side="right")

        self.groq_text = ctk.CTkTextbox(
            right, font=ctk.CTkFont(family="Segoe UI", size=17),
            fg_color="transparent", text_color=TEXT, wrap="word"
        )
        self.groq_text.pack(fill="both", expand=True, padx=15, pady=(0, 20))

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
        self.q_label.configure(text=q['question'])

        self._set_groq_text("Responde la pregunta para ver el análisis de Groq.")
        self.groq_status.configure(text="")

        self.answer_buttons = []
        for i, ans in enumerate(q['answers']):
            ans_text = f"{chr(65+i)}.  {ans}"
            wrapped_text = textwrap.fill(ans_text, width=90)
            lines = wrapped_text.count('\n') + 1
            btn_height = max(50, lines * 25)

            btn = ctk.CTkButton(
                self.buttons_frame,
                text=wrapped_text,
                font=ctk.CTkFont(family="Segoe UI", size=15),
                fg_color="#2a2a2a", hover_color="#3a3a3a", text_color=TEXT,
                anchor="w", height=btn_height,
                command=lambda idx=i: self.check_answer(idx)
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
                btn.configure(fg_color=SUCCESS, hover_color=SUCCESS, text_color="white", state="disabled")
            elif i == selected_idx:
                btn.configure(fg_color=ERROR, hover_color=ERROR, text_color="white", state="disabled")
            else:
                btn.configure(state="disabled")

        is_last = self.current_idx >= len(self.questions) - 1
        self.next_button.configure(
            state="normal", fg_color=ACCENT, text_color="white",
            text="Finalizar" if is_last else "Siguiente →"
        )

        self.groq_status.configure(text="⏳ consultando...")
        self._set_groq_text("")
        threading.Thread(
            target=self._ask_groq,
            args=(q,),
            daemon=True
        ).start()

    def _ask_groq(self, q):
        try:
            client = Groq(api_key=self.api_key)

            opciones = "\n".join(
                [f"  {chr(65+i)}. {ans}" + (" (CORRECTA)" if i == q['correct_index'] else "")
                 for i, ans in enumerate(q['answers'])]
            )
            prompt = (
                "Actúa como un profesor experto y explica la siguiente pregunta de tipo test.\n\n"
                f"PREGUNTA:\n\"{q['question']}\"\n\n"
                f"OPCIONES:\n{opciones}\n\n"
                "Tu tarea es explicar la respuesta de forma clara y concisa usando EXACTAMENTE el siguiente formato (no añadas saludos, ni introducciones, ni repitas 'La respuesta correcta es...'):\n\n"
                "✅ RESPUESTA CORRECTA\n"
                "[Indica solo la letra y el concepto de la respuesta correcta de forma directa]\n\n"
                "📖 CONTEXTO\n"
                "[Explica el porqué de la respuesta correcta y el concepto teórico subyacente de forma educativa]\n\n"
                "❌ OPCIONES INCORRECTAS\n"
                "[Explica brevemente por qué las otras opciones no son válidas, usando viñetas para cada una]"
            )

            chat = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512
            )
            result_text = chat.choices[0].message.content

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
