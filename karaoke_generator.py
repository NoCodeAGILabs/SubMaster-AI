import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Canvas, colorchooser
import tkinter.font as tkfont
import whisper
import os
from functools import lru_cache 
from moviepy import VideoFileClip 
import numpy as np
import pygame
import threading
import time
from difflib import SequenceMatcher
import sys
import re
import gc
import subprocess
import traceback
try:
    import moviepy.video.io.ffmpeg_tools as ffmpeg_tools
except ImportError:
    pass 
import subprocess as sp
import tempfile
from scipy.io import wavfile
import random
import logging
import warnings

# --- IMPORTS NECESARIOS ---
import imageio_ffmpeg
from PIL import ImageFont 
import platform 

# --- CONFIGURACIÓN OPTIMIZADA ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
warnings.filterwarnings("ignore")

# Detectar Sistema Operativo
IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# Configuración dinámica de FFmpeg
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
FFMPEG_DIR = os.path.dirname(FFMPEG_EXE)

# Extensiones
EXE_EXT = ".exe" if IS_WINDOWS else ""

FFPROBE_EXE = os.path.join(FFMPEG_DIR, f"ffprobe{EXE_EXT}")
FFPLAY_EXE  = os.path.join(FFMPEG_DIR, f"ffplay{EXE_EXT}")

# Fallbacks
if not os.path.exists(FFPLAY_EXE): FFPLAY_EXE = "ffplay"
if not os.path.exists(FFPROBE_EXE): FFPROBE_EXE = "ffprobe"

os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ["PATH"]
os.environ["IMAGEIO_FFMPEG_EXE"]  = FFMPEG_EXE
os.environ["IMAGEIO_FFPROBE_EXE"] = FFPROBE_EXE

@lru_cache(maxsize=64)
def get_cached_font(font_path, font_size):
    try: return ImageFont.truetype(font_path, font_size)
    except: return ImageFont.load_default()

# --- UTILIDADES ---

def open_folder_cross_platform(path):
    folder = os.path.dirname(path)
    try:
        if IS_WINDOWS:
            os.startfile(folder)
        elif IS_MAC:
            subprocess.run(["open", folder])
        else: # Linux
            subprocess.run(["xdg-open", folder])
    except Exception as e:
        print(f"No se pudo abrir la carpeta: {e}")

def normalize_text(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    return text

def split_syllables(word: str) -> list:
    pieces = re.findall(r'[^aeiouáéíóú]*[aeiouáéíóú]+[^aeiouáéíóú]*', word.lower(), flags=re.I)
    return pieces or [word]

def sanitize_float(val):
    try: return float(val)
    except: return 0.0

def refine_word_segments(words):
    if not words: return []
    refined = []
    for w in words:
        text = w['text'].strip()
        start = sanitize_float(w['start'])
        end = sanitize_float(w['end'])
        refined.append({'text': text, 'start': start, 'end': end})
    
    refined.sort(key=lambda x: x['start'])
    
    for i in range(len(refined)):
        if refined[i]['end'] <= refined[i]['start']:
            refined[i]['end'] = refined[i]['start'] + 0.2
        if i < len(refined) - 1:
            if refined[i]['end'] > refined[i+1]['start']:
                refined[i]['end'] = refined[i+1]['start'] - 0.01
                if refined[i]['end'] <= refined[i]['start']:
                     refined[i]['end'] = refined[i]['start'] + 0.1
                     refined[i+1]['start'] = refined[i]['end'] + 0.01
    return refined

# --- TRADUCCIONES ---
TRANSLATIONS = {
    'es': {
        'app_title': 'SubMaster AI',
        'editor_title': 'EDITOR VISUAL / PREVIEW - SubMaster AI',
        'undo': 'DESHACER', 'redo': 'REHACER', 'cancel': 'CERRAR', 'save': 'GUARDAR',
        'preview': 'PREVIEW', 'controls': 'CONTROLES', 'edit': 'EDITAR', 'timeline': 'LÍNEA DE TIEMPO',
        'config': 'CONFIGURACIÓN AVANZADA', 'lyrics': 'LETRA (PEGAR AQUÍ PARA FORZAR SINCRONIZACIÓN)', 
        'transcribe': 'PROCESAR (IA + TEXTO)',
        'visual_editor': '👁️ EDITOR / PREVIEW', # CAMBIO AQUÍ PARA QUE SEA CLARO
        'export_subs': 'EXPORTAR SUBS', 'generate_video': 'RENDERIZAR VIDEO',
        'select_video': 'SELECCIONAR VIDEO', 'no_video': 'Ningún video seleccionado', 'lang_btn': '🌐 IDIOMA: ES', 
        'video_success': '¡Video generado!', 'confirm_delete': '¿Borrar palabra?',
        'model': 'Modelo:', 'font': 'Fuente:', 'active': 'Color Activo:', 'inactive': 'Color Pasivo:', 
        'effect': 'Efecto:', 'size': 'Tamaño:', 'position': 'Posición:', 
        
        'visible_words': 'Cant. Palabras:',
        'single': 'Una Palabra (1)',      
        'compact': 'Compacto (4)',
        'balanced': 'Balanceado (7)',
        'full': 'Completo (11)',
        
        'audio': 'AUDIO', 'language': 'Idioma:',
        'text': 'Texto:', 'start': 'Inicio (s):', 'end': 'Fin (s):',
        'voc_rem': 'QUITAR VOZ', 'rendering': 'Renderizando (Espera)...',
        'log_dl': 'Descargando Modelo IA (Puede tardar minutos)...', 'log_tr': 'Transcribiendo (Modo CPU)...', 'log_al': 'Alineando Texto...',
        
        'fx_color': 'Clásico (Color)', 'fx_wipe': 'Karaoke Barrido', 'fx_bounce': 'Rebote Suave',
        'fx_neon': 'Resplandor Neón', 'fx_type': 'Máquina de Escribir', 'fx_scatter': 'Disperso (Caos)',
        'fx_hormozi': 'Estilo Hormozi (1 Palabra)', 'fx_ball': 'Pelota Saltarina',
        'fx_box': 'Fondo de Caja (TikTok)', 'fx_pop': 'Pop-Up (MrBeast)',
        'fx_shake': 'Temblor (Shake)', 'fx_glitch': 'Glitch Digital',
        'fx_slide': 'Deslizar Arriba', 'fx_heart': 'Marcador Corazón',
        'fx_fade': 'Fade In/Out', 'fx_pulse': 'Pulsación', 'fx_zoom': 'Zoom Dramático'
    },
    'en': {
        'app_title': 'SubMaster AI',
        'editor_title': 'VISUAL EDITOR / PREVIEW - SubMaster AI',
        'undo': 'UNDO', 'redo': 'REDO', 'cancel': 'CLOSE', 'save': 'SAVE',
        'preview': 'PREVIEW', 'controls': 'CONTROLS', 'edit': 'EDIT', 'timeline': 'TIMELINE',
        'config': 'ADVANCED CONFIG', 'lyrics': 'LYRICS (PASTE TO FORCE SYNC)', 
        'transcribe': 'PROCESS (AI + TEXT)',
        'visual_editor': '👁️ EDITOR / PREVIEW', 
        'export_subs': 'EXPORT SUBS', 'generate_video': 'RENDER VIDEO',
        'select_video': 'SELECT VIDEO', 'no_video': 'No video selected', 'lang_btn': '🌐 LANG: EN', 
        'video_success': 'Video generated!', 'confirm_delete': 'Delete word?',
        'model': 'Model:', 'font': 'Font:', 'active': 'Active Color:', 'inactive': 'Passive Color:', 
        'effect': 'Effect:', 'size': 'Size:', 'position': 'Position:', 
        
        'visible_words': 'Word Count:',
        'single': 'Single Word (1)',      
        'compact': 'Compact (4)',
        'balanced': 'Balanced (7)',
        'full': 'Full (11)',

        'visible_words': 'Visible Words:', 'audio': 'AUDIO', 'language': 'Language:',
        'text': 'Text:', 'start': 'Start (s):', 'end': 'End (s):',
        'voc_rem': 'REMOVE VOCALS', 'rendering': 'Rendering (Wait)...',
        'log_dl': 'Downloading AI Model (May take minutes)...', 'log_tr': 'Transcribing (CPU Mode)...', 'log_al': 'Aligning...',
        
        'fx_color': 'Classic (Color)', 'fx_wipe': 'Karaoke Wipe', 'fx_bounce': 'Smooth Bounce',
        'fx_neon': 'Neon Glow', 'fx_type': 'Typewriter', 'fx_scatter': 'Scattered Chaos',
        'fx_hormozi': 'Hormozi Style (1 Word)', 'fx_ball': 'Bouncing Ball',
        'fx_box': 'Box Background (TikTok)', 'fx_pop': 'Pop-Up (MrBeast)',
        'fx_shake': 'Intense Shake', 'fx_glitch': 'Digital Glitch',
        'fx_slide': 'Slide Up', 'fx_heart': 'Heart Marker',
        'fx_fade': 'Fade In/Out', 'fx_pulse': 'Pulse', 'fx_zoom': 'Dramatic Zoom'
    }
}

EFFECT_KEYS = [
    'fx_color', 'fx_wipe', 'fx_bounce', 'fx_neon', 'fx_type', 
    'fx_scatter', 'fx_hormozi', 'fx_ball', 
    'fx_box', 'fx_pop', 'fx_shake', 'fx_glitch', 'fx_slide', 'fx_heart',
    'fx_fade', 'fx_pulse', 'fx_zoom'
]

# --- PARCHE FFMPEG ---
try:
    def ffplay_version_patch(): return ("ffplay", "6.0")
    if 'ffmpeg_tools' in globals():
        ffmpeg_tools.ffplay_version = ffplay_version_patch
except: pass

_Original_Popen = sp.Popen
def patched_popen(cmd, *a, **kw):
    if isinstance(cmd, (list, tuple)) and len(cmd) > 0:
        cmd = list(cmd)
        prog = str(cmd[0]).lower()
        if prog == "ffplay": cmd[0] = FFPLAY_EXE
        elif prog == "ffmpeg": cmd[0] = FFMPEG_EXE
    elif isinstance(cmd, str):
        prog = cmd.strip().lower()
        if prog.startswith("ffplay"): cmd = cmd.replace("ffplay", FFPLAY_EXE, 1)
        elif prog.startswith("ffmpeg"): cmd = cmd.replace("ffmpeg", FFMPEG_EXE, 1)
    if "executable" in kw:
        exe = str(kw["executable"]).lower()
        if exe == "ffplay": kw["executable"] = FFPLAY_EXE
        elif exe == "ffmpeg": kw["executable"] = FFMPEG_EXE
    return _Original_Popen(cmd, *a, **kw)
sp.Popen = patched_popen

# ==============================================================================
# TIMELINE EDITOR
# ==============================================================================
class TimelineEditor:
    def __init__(self, parent, words_data, video_path, on_save_callback, language='es'):
        self.window = tk.Toplevel(parent)
        self.lang = language
        self.trans = TRANSLATIONS[language]
        self.window.title(f"⚡ {self.trans['editor_title']}")
        self.window.geometry("1600x900")
        self.window.configure(bg='#0a0e27')
        
        self.words_data = refine_word_segments(words_data.copy())
        self.video_path = video_path
        self.on_save = on_save_callback
        self.sel_idx = None
        
        self.playing = False
        self.start_time = 0.0
        self.offset = 0.0
        self.px_per_sec = 180.0 
        
        self.history = [self.words_data.copy()]
        self.hist_idx = 0
        
        pygame.mixer.init()
        self.audio_file = None
        self.inst_file = None 
        
        self.setup_ui()
        self.load_audio()
        
        self.window.after(200, self.draw_static_timeline) 
        
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind('<space>', self.toggle_play_event)
        self.window.bind('<Control-z>', lambda e: self.undo())
        self.window.bind('<Control-y>', lambda e: self.redo())
        self.window.bind('<Left>', lambda e: self.scroll(-1))
        self.window.bind('<Right>', lambda e: self.scroll(1))
        
        self.window.focus_set()

    def setup_ui(self):
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1) 
        self.window.rowconfigure(2, weight=1) 

        head = tk.Frame(self.window, bg='#0f1629', height=50)
        head.grid(row=0, column=0, sticky='ew')
        tk.Button(head, text=self.trans['save'], command=self.save, bg='#00ff88', fg='black', font=('bold',10)).pack(side=tk.RIGHT, padx=10, pady=10)
        tk.Button(head, text=self.trans['undo'], command=self.undo, bg='#333', fg='white').pack(side=tk.RIGHT, padx=5)
        tk.Button(head, text=self.trans['redo'], command=self.redo, bg='#333', fg='white').pack(side=tk.RIGHT, padx=5)

        top = tk.Frame(self.window, bg='#0a0e27')
        top.grid(row=1, column=0, sticky='nsew', padx=10, pady=10)
        
        self.cv_prev = Canvas(top, bg='black', highlightthickness=0)
        self.cv_prev.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        pnl = tk.Frame(top, bg='#151b35', width=350)
        pnl.pack(side=tk.RIGHT, fill=tk.Y, padx=(10,0))
        
        tk.Label(pnl, text=self.trans['controls'], bg='#00ff88', fg='black', font=('bold',10)).pack(fill=tk.X)
        ctr = tk.Frame(pnl, bg='#151b35', pady=10); ctr.pack(fill=tk.X)
        tk.Button(ctr, text="▶ / ⏸", command=self.toggle_play, bg='#00ff88', font=('Arial', 16), width=6).pack(pady=5)
        
        row_aud = tk.Frame(ctr, bg='#151b35')
        row_aud.pack(pady=5)
        tk.Button(row_aud, text="⏹", command=self.stop, bg='#ff4444', font=('Arial', 12), width=4).pack(side=tk.LEFT, padx=2)
        tk.Button(row_aud, text="🎤 "+self.trans['voc_rem'], command=self.remove_vocals, bg='#2196f3', fg='white', font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=2)
        
        self.lbl_time = tk.Label(ctr, text="00:00 / 00:00", bg='#151b35', fg='#00ff88', font=('Consolas', 22, 'bold'))
        self.lbl_time.pack(pady=10)
        self.lbl_sec = tk.Label(ctr, text="(0.0000s)", bg='#151b35', fg='white', font=('Consolas', 12))
        self.lbl_sec.pack()

        tk.Label(pnl, text=self.trans['edit'], bg='#00ff88', fg='black', font=('bold',10)).pack(fill=tk.X, pady=(20,0))
        ed = tk.Frame(pnl, bg='#151b35', pady=10); ed.pack(fill=tk.X)
        
        self.v_txt = tk.StringVar()
        self.v_start = tk.DoubleVar()
        self.v_end = tk.DoubleVar()
        
        self.mk_inp(ed, self.trans['text'], self.v_txt)
        self.mk_spin(ed, self.trans['start'], self.v_start)
        self.mk_spin(ed, self.trans['end'], self.v_end)
        
        tk.Button(ed, text="✓ APLICAR", command=self.apply_edit, bg='#00ff88', font=('bold',10)).pack(fill=tk.X, padx=10, pady=5)
        tk.Button(ed, text="🗑 BORRAR", command=self.delete_word, bg='#ff4444', fg='white', font=('bold',10)).pack(fill=tk.X, padx=10, pady=5)
        tk.Button(ed, text="+ NUEVA", command=self.add_word, bg='#2196f3', fg='white', font=('bold',10)).pack(fill=tk.X, padx=10, pady=5)

        bot = tk.Frame(self.window, bg='#0a0e27')
        bot.grid(row=2, column=0, sticky='nsew', padx=10, pady=(0,10))
        tk.Label(bot, text=self.trans['timeline'], bg='#00ff88', fg='black', font=('bold',10)).pack(fill=tk.X)
        
        cv_fr = tk.Frame(bot, bg='#151b35')
        cv_fr.pack(fill=tk.BOTH, expand=True)
        
        self.h_scr = tk.Scrollbar(cv_fr, orient=tk.HORIZONTAL)
        self.cv_tl = Canvas(cv_fr, bg='#0f121f', highlightthickness=0, xscrollcommand=self.h_scr.set, height=300)
        self.h_scr.config(command=self.cv_tl.xview)
        
        self.h_scr.pack(side=tk.BOTTOM, fill=tk.X)
        self.cv_tl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.cv_tl.bind('<Button-1>', self.on_click)
        self.cv_tl.bind('<B1-Motion>', self.on_drag)

    def mk_inp(self, p, l, v):
        tk.Label(p, text=l, bg='#151b35', fg='gray').pack(anchor='w', padx=10)
        tk.Entry(p, textvariable=v, bg='#0a0e27', fg='white', relief='flat', insertbackground='white').pack(fill=tk.X, padx=10, pady=(0,5))
    def mk_spin(self, p, l, v):
        tk.Label(p, text=l, bg='#151b35', fg='gray').pack(anchor='w', padx=10)
        tk.Spinbox(p, textvariable=v, from_=0, to=99999, increment=0.0001, format="%.4f", bg='#0a0e27', fg='white', buttonbackground='#333').pack(fill=tk.X, padx=10, pady=(0,5))
    def scroll(self, d): self.cv_tl.xview_scroll(d, "units")

    def load_audio(self):
        try:
            with VideoFileClip(self.video_path) as v:
                # CORREGIDO: Guardar como WAV para que scipy no falle
                self.audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
                v.audio.write_audiofile(self.audio_file, fps=44100, logger=None)
            self.dur = pygame.mixer.Sound(self.audio_file).get_length()
        except: self.dur = 60.0
        
        min_tot, sec_tot = divmod(self.dur, 60)
        self.lbl_time.config(text=f"00:00 / {int(min_tot):02}:{int(sec_tot):02}")

    def remove_vocals(self):
        if not self.audio_file: return
        if not messagebox.askyesno("Karaoke", "Eliminar voces puede tardar. ¿Continuar?"): return
        threading.Thread(target=self._voc_thread, daemon=True).start()

    def _voc_thread(self):
        try:
            # Scipy ahora podrá leer el archivo porque es .wav
            fs, data = wavfile.read(self.audio_file)
            if data.ndim > 1: 
                inst = (data.T[0] - data.T[1]) / 2
                self.inst_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
                m = np.max(np.abs(inst))
                if m > 0: inst = np.int16(inst/m*32767*0.8)
                wavfile.write(self.inst_file, fs, np.column_stack((inst, inst)))
                messagebox.showinfo("OK", "Voces reducidas (Modo Preview).")
            else:
                messagebox.showwarning("Error", "Audio Mono detectado.")
        except Exception as e:
            print(e)
            messagebox.showerror("Error", f"Error eliminando voz: {e}")

    def draw_static_timeline(self):
        self.cv_tl.delete('all')
        if not self.words_data: return
        
        # Forzar conversión a float puro de Python para evitar errores de Numpy
        duracion_total = float(max(self.dur, self.words_data[-1]['end'] + 2))
        total_w = int(duracion_total * self.px_per_sec)
        
        self.cv_tl.config(scrollregion=(0, 0, total_w, 500))
        
        # Dibujar Regla de Tiempo
        for i in range(int(duracion_total) + 1):
            x = 50 + i * self.px_per_sec
            self.cv_tl.create_line(x, 0, x, 300, fill='#444')
            self.cv_tl.create_text(x, 15, text=str(i), fill='#888', font=('Arial', 8))
            for d in range(1, 10):
                sx = x + (d * self.px_per_sec / 10)
                self.cv_tl.create_line(sx, 0, sx, 10, fill='#222')
        
        # Dibujar Palabras en Zig-Zag
        base_y = 50
        for i, w in enumerate(self.words_data):
            # Casting explícito a float y luego int para coordenadas
            start_t = float(w['start'])
            end_t = float(w['end'])
            
            x1 = int(50 + start_t * self.px_per_sec)
            x2 = int(50 + end_t * self.px_per_sec)
            
            # Asegurar ancho mínimo de 2 pixeles para que se vea
            if x2 - x1 < 2: x2 = x1 + 2
            w_px = x2 - x1
            
            # Lógica ZIG-ZAG: Alternar altura para que no se encimen los textos
            # Las pares van arriba, las impares abajo
            if i % 2 == 0:
                y = base_y
            else:
                y = base_y + 40  # 40 pixeles más abajo
            
            col = '#00ff88' if i == self.sel_idx else '#333'
            txt_c = 'black' if i == self.sel_idx else 'white'
            outline_c = 'white' if i == self.sel_idx else '#666'
            tag = f"w_{i}"
            
            # Caja
            self.cv_tl.create_rectangle(x1, y, x1+w_px, y+30, fill=col, outline=outline_c, tags=tag)
            
            # Texto (Centrado en la caja)
            # Si la caja es muy chica, el texto se saldrá, pero como está en ZigZag ya no tapará al vecino
            self.cv_tl.create_text(x1 + w_px/2, y + 15, text=w['text'], fill=txt_c, font=('Arial', 9, 'bold'), tags=tag)

        # Cursor rojo
        self.cv_tl.create_line(50, 0, 50, 300, fill='red', width=2, tags='cursor')

    def update_cursor(self, t):
        x = 50 + t * self.px_per_sec
        self.cv_tl.coords('cursor', x, 0, x, 300)
        vis_x = self.cv_tl.canvasx(0)
        w = self.cv_tl.winfo_width()
        if x > vis_x + w - 100 or x < vis_x:
            self.cv_tl.xview_moveto((x - 100) / (self.dur * self.px_per_sec))

    def clock_loop(self):
        if not self.playing: return
        t = self.offset + (time.time() - self.start_time)
        if t > self.dur: self.stop(); return
        
        min_cur, sec_cur = divmod(t, 60)
        min_tot, sec_tot = divmod(self.dur, 60)
        
        time_str = f"{int(min_cur):02}:{int(sec_cur):02} / {int(min_tot):02}:{int(sec_tot):02}"
        self.lbl_time.config(text=time_str)
        
        self.lbl_sec.config(text=f"({t:.4f}s)")
        
        self.update_cursor(t)
        self.cv_prev.delete('all')
        act = next((w for w in self.words_data if w['start'] <= t <= w['end']), None)
        if act:
            self.cv_prev.create_text(self.cv_prev.winfo_width()/2, 100, text=act['text'], fill='#00ff88', font=('Arial', 36, 'bold'))
        self.window.after(30, self.clock_loop)

    def toggle_play(self):
        if not self.audio_file: return
        to_play = self.inst_file if (self.inst_file and os.path.exists(self.inst_file)) else self.audio_file
        if self.playing:
            self.offset += time.time() - self.start_time
            pygame.mixer.music.pause()
            self.playing = False
        else:
            pygame.mixer.music.load(to_play)
            pygame.mixer.music.play(start=self.offset)
            self.start_time = time.time()
            self.playing = True
            self.clock_loop()

    def toggle_play_event(self, e):
        focused = self.window.focus_get()
        if isinstance(focused, (tk.Entry, tk.Spinbox, tk.Text)): return 
        self.toggle_play()

    def stop(self):
        pygame.mixer.music.stop()
        self.playing = False
        self.offset = 0
        self.update_cursor(0)
        min_tot, sec_tot = divmod(self.dur, 60)
        self.lbl_time.config(text=f"00:00 / {int(min_tot):02}:{int(sec_tot):02}")

    def on_click(self, e):
        self.window.focus_set()
        x = self.cv_tl.canvasx(e.x); y = self.cv_tl.canvasy(e.y)
        item = self.cv_tl.find_closest(x, y)
        tags = self.cv_tl.gettags(item)
        clicked = False
        for t in tags:
            if t.startswith('w_'):
                self.sel_idx = int(t.split('_')[1])
                w = self.words_data[self.sel_idx]
                self.v_txt.set(w['text']); self.v_start.set(w['start']); self.v_end.set(w['end'])
                self.draw_static_timeline()
                clicked = True; break
        if not clicked or y < 40:
            t = max(0, (x - 50) / self.px_per_sec)
            self.offset = t
            if self.playing:
                pygame.mixer.music.stop()
                to_play = self.inst_file if (self.inst_file and os.path.exists(self.inst_file)) else self.audio_file
                pygame.mixer.music.load(to_play)
                pygame.mixer.music.play(start=t)
                self.start_time = time.time()
            self.update_cursor(t)
            min_cur, sec_cur = divmod(t, 60)
            min_tot, sec_tot = divmod(self.dur, 60)
            time_str = f"{int(min_cur):02}:{int(sec_cur):02} / {int(min_tot):02}:{int(sec_tot):02}"
            self.lbl_time.config(text=time_str)

    def on_drag(self, e): self.on_click(e)

    def apply_edit(self):
        if self.sel_idx is None: return
        self.save_hist()
        w = self.words_data[self.sel_idx]
        w['text'] = self.v_txt.get()
        w['start'] = self.v_start.get()
        w['end'] = self.v_end.get()
        self.words_data = refine_word_segments(self.words_data)
        self.sel_idx = None
        self.draw_static_timeline()
        self.window.focus_set()

    def delete_word(self):
        if self.sel_idx is None: return
        self.save_hist()
        del self.words_data[self.sel_idx]
        self.sel_idx = None
        self.draw_static_timeline()
        self.window.focus_set()

    def add_word(self):
        self.save_hist()
        t = self.offset
        self.words_data.append({'text': 'NEW', 'start': t, 'end': t+1})
        self.words_data = refine_word_segments(self.words_data)
        self.draw_static_timeline()
        self.window.focus_set()

    def save_hist(self):
        self.history = self.history[:self.hist_idx+1]
        self.history.append([w.copy() for w in self.words_data])
        self.hist_idx += 1

    def undo(self):
        if self.hist_idx > 0:
            self.hist_idx -= 1; self.words_data = [w.copy() for w in self.history[self.hist_idx]]; self.draw_static_timeline()
    def redo(self):
        if self.hist_idx < len(self.history)-1:
            self.hist_idx += 1; self.words_data = [w.copy() for w in self.history[self.hist_idx]]; self.draw_static_timeline()
    def save(self): self.on_save(self.words_data); self.close()
    def close(self):
        pygame.mixer.music.stop()
        try: os.remove(self.audio_file)
        except: pass
        if self.inst_file:
            try: os.remove(self.inst_file)
            except: pass
        self.window.destroy(); gc.collect()

# ==============================================================================
# MAIN APP
# ==============================================================================
class KaraokeGenerator:
    def __init__(self, root):
        self.root = root
        self.lang = 'es'
        self.words = []
        self.vid_path = None
        self.root.title("SubMaster AI")
        self.root.geometry("1100x900")
        self.root.configure(bg='#0a0e27')
        self.ui()

    def ui(self):
        fr = tk.Frame(self.root, bg='#0a0e27', padx=20, pady=20)
        fr.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(fr, text=TRANSLATIONS[self.lang]['app_title'], font=('Impact', 28), bg='#0a0e27', fg='white').pack(pady=(0,10))
        tk.Button(fr, text=TRANSLATIONS[self.lang]['lang_btn'], command=self.swap_lang, bg='#151b35', fg='white').pack(anchor='ne')
        
        cf = tk.Frame(fr, bg='#151b35', padx=10, pady=10); cf.pack(fill=tk.X, pady=5)
        self.lbl_v = tk.Label(cf, text=TRANSLATIONS[self.lang]['no_video'], bg='#151b35', fg='gray')
        self.lbl_v.pack(side=tk.LEFT)
        tk.Button(cf, text=TRANSLATIONS[self.lang]['select_video'], command=self.sel_vid, bg='#00ff88').pack(side=tk.RIGHT)
        
        st = tk.Frame(fr, bg='#151b35', padx=10, pady=10); st.pack(fill=tk.X, pady=5)
        self.v_mod = tk.StringVar(value='small')
        self.mk_cb(st, TRANSLATIONS[self.lang]['model'], self.v_mod, ['tiny', 'base', 'small'])
        self.v_font = tk.StringVar(value='Arial')
        self.mk_cb(st, TRANSLATIONS[self.lang]['font'], self.v_font, sorted(tkfont.families()))
        self.font_p = tk.Label(st, text="Abc", bg='black', fg='white', font=('Arial',12))
        self.font_p.pack(side=tk.LEFT, padx=5)
        self.v_font.trace('w', lambda *a: self.font_p.config(font=(self.v_font.get(),12)))
        
        self.v_ef = tk.StringVar(value=TRANSLATIONS[self.lang]['fx_color'])
        efs = [TRANSLATIONS[self.lang][k] for k in EFFECT_KEYS]
        self.mk_cb(st, TRANSLATIONS[self.lang]['effect'], self.v_ef, efs)
        
        cp = tk.Frame(fr, bg='#151b35', padx=10, pady=10); cp.pack(fill=tk.X, pady=5)
        self.c_act = tk.StringVar(value='#00ff00'); self.mk_col(cp, TRANSLATIONS[self.lang]['active'], self.c_act)
        self.c_pas = tk.StringVar(value='#ffffff'); self.mk_col(cp, TRANSLATIONS[self.lang]['inactive'], self.c_pas)
        self.v_sz = tk.IntVar(value=60)
        tk.Label(cp, text=TRANSLATIONS[self.lang]['size'], bg='#151b35', fg='white').pack(side=tk.LEFT)
        tk.Spinbox(cp, textvariable=self.v_sz, from_=10, to=200, width=5).pack(side=tk.LEFT)
        self.v_pos = tk.StringVar(value='bottom')
        for p in ['bottom', 'top', 'center', 'alternating']:
            t = '⬇' if p=='bottom' else ('⬆' if p=='top' else ('⬍' if p=='center' else '⇅'))
            tk.Radiobutton(cp, text=t, variable=self.v_pos, value=p, bg='#151b35', fg='white', selectcolor='#00ff88').pack(side=tk.LEFT)

        row_vis = tk.Frame(fr, bg='#151b35', padx=10, pady=10); row_vis.pack(fill=tk.X, pady=5)
        self.v_vis = tk.StringVar(value=TRANSLATIONS[self.lang]['balanced'])
        vis_opts = [
            TRANSLATIONS[self.lang]['single'], 
            TRANSLATIONS[self.lang]['compact'], 
            TRANSLATIONS[self.lang]['balanced'], 
            TRANSLATIONS[self.lang]['full']
        ]
        self.mk_cb(row_vis, TRANSLATIONS[self.lang]['visible_words'], self.v_vis, vis_opts)

        tk.Label(fr, text=TRANSLATIONS[self.lang]['lyrics'], bg='#0a0e27', fg='#00ff88').pack(anchor='w')
        self.txt = scrolledtext.ScrolledText(fr, height=8, bg='#0f121f', fg='white', insertbackground='white')
        self.txt.pack(fill=tk.BOTH, expand=True)
        
        self.b_run = tk.Button(fr, text="🚀 "+TRANSLATIONS[self.lang]['transcribe'], command=self.run, bg='#00ff88', font=('bold',12), pady=5)
        self.b_run.pack(fill=tk.X, pady=10)
        
        b2 = tk.Frame(fr, bg='#0a0e27'); b2.pack(fill=tk.X)
        self.b_ed = tk.Button(b2, text="✏️ "+TRANSLATIONS[self.lang]['visual_editor'], command=self.open_ed, bg='#ff9800', state='disabled')
        self.b_ed.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.b_ex = tk.Button(b2, text="📄 "+TRANSLATIONS[self.lang]['export_subs'], command=self.exp, bg='#2196f3', state='disabled')
        self.b_ex.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.b_rn = tk.Button(b2, text="🎬 "+TRANSLATIONS[self.lang]['generate_video'], command=self.gen, bg='#f44336', state='disabled')
        self.b_rn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        self.pb = ttk.Progressbar(fr, mode='indeterminate'); self.pb.pack(fill=tk.X, pady=5)
        self.log_l = tk.Label(fr, text="Ready.", bg='#0a0e27', fg='gray'); self.log_l.pack(anchor='w')

    def mk_cb(self, p, l, v, vals):
        tk.Label(p, text=l, bg='#151b35', fg='white').pack(side=tk.LEFT)
        ttk.Combobox(p, textvariable=v, values=vals, width=20).pack(side=tk.LEFT, padx=5)
    def mk_col(self, p, l, v):
        tk.Label(p, text=l, bg='#151b35', fg='white').pack(side=tk.LEFT)
        b = tk.Label(p, bg=v.get(), width=3, relief='solid'); b.pack(side=tk.LEFT, padx=5)
        b.bind("<Button-1>", lambda e: (c := colorchooser.askcolor(v.get())[1], v.set(c) if c else None, b.config(bg=v.get())))

    def sel_vid(self):
        f = filedialog.askopenfilename()
        if f: 
            self.vid_path = f
            self.lbl_v.config(text=os.path.basename(f), fg='white')
            
            # --- CORREGIDO: USAR MOVIEPY PARA DETECTAR RESOLUCIÓN (100% SEGURO) ---
            try:
                # Usamos with para asegurar que el archivo se cierra
                with VideoFileClip(f) as clip:
                    width = clip.w
                    height = clip.h
                
                t = TRANSLATIONS[self.lang]
                
                if height > width:
                    # Vertical -> Compacto
                    self.v_vis.set(t['compact']) 
                    self.log_l.config(text="📱 Vertical detected: Compact mode set.")
                else:
                    # Horizontal -> Balanceado
                    self.v_vis.set(t['balanced'])
                    self.log_l.config(text="💻 Horizontal detected: Balanced mode set.")
                    
            except Exception as e:
                # Si falla moviepy (raro), simplemente no cambiamos el modo y logueamos
                print(f"Warning: Resolution detection failed: {e}")
                self.log_l.config(text="Video loaded.")
    
    def swap_lang(self):
        self.lang = 'en' if self.lang == 'es' else 'es'
        for widget in self.root.winfo_children(): widget.destroy()
        self.ui()

    def run(self):
        if not self.vid_path: return
        self.b_run.config(state='disabled'); self.pb.start(10)
        threading.Thread(target=self.process, daemon=True).start()

    def safe_log(self, t): self.root.after(0, lambda: self.log_l.config(text=t))

    def process(self):
        try:
            self.safe_log(TRANSLATIONS[self.lang]['log_dl'])
            
            try:
                subprocess.run([FFMPEG_EXE, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except Exception as e:
                raise RuntimeError(f"Error crítico: No se puede ejecutar FFmpeg en la ruta: {FFMPEG_EXE}.\nDetalle: {e}")

            model = whisper.load_model(self.v_mod.get())
            
            self.safe_log(TRANSLATIONS[self.lang]['log_tr'])
            res = model.transcribe(self.vid_path, word_timestamps=True, fp16=False)
            
            # Palabras crudas de la IA
            raw = [{'text': w['word'], 'start': w['start'], 'end': w['end']} for s in res['segments'] for w in s['words']]
            
            ly = self.txt.get("1.0", tk.END).strip()
            
            # --- LÓGICA DE PROTECCIÓN ---
            usar_texto_usuario = False
            
            if ly:
                self.safe_log("Analizando similitud...")
                # Normalizamos para comparar peras con peras
                cl = [w for w in re.split(r'\s+', ly) if w]
                
                # Texto IA unido
                str_ai = " ".join([normalize_text(w['text']) for w in raw])
                # Texto Usuario unido
                str_user = " ".join([normalize_text(w) for w in cl])
                
                # Calculamos porcentaje de parecido (0.0 a 1.0)
                ratio = SequenceMatcher(None, str_ai, str_user).ratio()
                porcentaje = int(ratio * 100)
                
                if porcentaje < 40: # UMBRAL DE SEGURIDAD (40%)
                    msg = (f"⚠️ ALERTA DE DISCREPANCIA GRAVE ⚠️\n\n"
                           f"El texto que pegaste coincide solo un {porcentaje}% con el audio.\n\n"
                           f"Si continúas, el video quedará desincronizado.\n\n"
                           f"¿Qué deseas hacer?")
                    
                    respuesta = messagebox.askyesno("SubMaster AI - Seguridad", 
                                                    msg + "\n\nSÍ = Forzar mi texto (Riesgoso)\nNO = Ignorar mi texto y usar lo que escuchó la IA")
                    
                    if respuesta: # Dijo SÍ, forzar
                        usar_texto_usuario = True
                    else: # Dijo NO, usar IA
                        usar_texto_usuario = False
                        self.safe_log("Usando transcripción automática de IA...")
                else:
                    # Si el parecido es bueno, usamos el texto del usuario sin preguntar
                    usar_texto_usuario = True

            # --- ALINEACIÓN O USO DIRECTO ---
            if usar_texto_usuario and ly:
                self.safe_log(TRANSLATIONS[self.lang]['log_al'])
                cl = [w for w in re.split(r'\s+', ly) if w]
                wn = [normalize_text(w['text']) for w in raw]
                un = [normalize_text(w) for w in cl]
                sm = SequenceMatcher(None, wn, un)
                fin = []
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag == 'equal':
                        for k in range(j2-j1): fin.append({'text': cl[j1+k], 'start': raw[i1+k]['start'], 'end': raw[i1+k]['end']})
                    elif tag == 'replace':
                        if i2 > i1:
                            st, en = raw[i1]['start'], raw[i2-1]['end']
                            dur = (en-st)/(j2-j1)
                            for k in range(j2-j1): fin.append({'text': cl[j1+k], 'start': st+k*dur, 'end': st+(k+1)*dur})
                    elif tag == 'insert':
                        le = fin[-1]['end'] if fin else 0.0
                        for k in range(j2-j1): fin.append({'text': cl[j1+k], 'start': le, 'end': le+0.5}); le+=0.5
                self.words = fin
            else:
                # Usamos lo que escuchó la IA directamente
                self.words = raw
            
            self.words = refine_word_segments(self.words)
            self.safe_log(f"Done. {len(self.words)} words.")
            self.root.after(0, self.enable)

        except Exception:
            full_error = traceback.format_exc()
            print(full_error)
            self.safe_log("Error Crítico Detectado.")
            self.root.after(0, lambda: self.show_error_popup(full_error))

    def show_error_popup(self, error_text):
        err_win = tk.Toplevel(self.root)
        err_win.title("ERROR CRÍTICO - CÓPIALO Y ENVÍALO")
        err_win.geometry("800x600")
        
        lbl = tk.Label(err_win, text="Se ha producido un error. Copia el texto de abajo:", fg="red", font=("Arial", 12, "bold"))
        lbl.pack(pady=10)
        
        txt = scrolledtext.ScrolledText(err_win)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        txt.insert(tk.END, error_text)
        
        self.pb.stop()
        self.b_run.config(state='normal')

    def enable(self):
        self.pb.stop()
        self.b_run.config(state='normal')
        self.b_ed.config(state='normal'); self.b_ex.config(state='normal'); self.b_rn.config(state='normal')
        self.open_ed()

    def open_ed(self): TimelineEditor(self.root, self.words, self.vid_path, self.cb_save, self.lang)
    def cb_save(self, w): self.words = w; self.safe_log("Saved.")

    def exp(self):
        f = filedialog.asksaveasfilename(defaultextension=".srt")
        if f:
            if f.endswith('.srt'): self.save_srt(f)
            else: self.create_ass(f, self.words, (1920,1080))
            self.safe_log("Exported.")

    def save_srt(self, f):
        with open(f, 'w', encoding='utf-8') as file:
            for i, w in enumerate(self.words, 1):
                def ft(s): h,r=divmod(s,3600); m,s=divmod(r,60); return f"{int(h):02}:{int(m):02}:{s:06.3f}".replace('.',',')
                file.write(f"{i}\n{ft(w['start'])} --> {ft(w['end'])}\n{w['text']}\n\n")

    def gen(self):
        out = filedialog.asksaveasfilename(defaultextension=".mp4")
        if not out: return
        self.b_rn.config(state='disabled')
        self.pb.start(10)
        threading.Thread(target=self._gen_thread, args=(out,), daemon=True).start()

    def _gen_thread(self, out):
        self.safe_log(TRANSLATIONS[self.lang]['rendering'])
        try:
            ass = "t.ass"
            self.create_ass(ass, self.words, (1920,1080))
            
            cmd = [FFMPEG_EXE, "-i", self.vid_path, "-vf", f"ass={ass}", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "copy", "-y", out]
            
            if IS_WINDOWS:
                subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW, check=True)
            else:
                subprocess.run(cmd, check=True)
            
            if os.path.exists(ass): os.remove(ass)
            open_folder_cross_platform(out)
            self.safe_log("Success! Video saved.")
        except Exception as e:
            full_error = traceback.format_exc()
            self.safe_log(f"Render Error.")
            self.root.after(0, lambda: self.show_error_popup(full_error))
        finally:
            self.root.after(0, lambda: (self.pb.stop(), self.b_rn.config(state='normal')))

    def create_ass(self, filename, words, size):
        width, height = size
        sel_txt = self.v_ef.get()
        current_trans = TRANSLATIONS[self.lang]
        eff_key = next((k for k, v in current_trans.items() if v == sel_txt), 'fx_color')
        if eff_key not in EFFECT_KEYS: eff_key = 'fx_color'
        
        pos, font, sz = self.v_pos.get(), self.v_font.get(), self.v_sz.get()
        def ac(c): h=c.lstrip('#'); return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}"
        c_act = ac(self.c_act.get()); c_in = ac(self.c_pas.get())
        
        align, mv, ty = 2, 50, height - 100
        if pos == 'top': align, mv, ty = 8, 50, 150
        elif pos == 'center': align, mv, ty = 5, 0, height // 2
        
        border_style = "3" if eff_key == 'fx_box' else "1"
        back_col = "&H80000000" if eff_key == 'fx_box' else "&H00000000"
        
        head = f"""[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,{font},{sz},{c_act},{c_in},&H00000000,{back_col},-1,0,0,0,100,100,0,0,{border_style},2,0,{align},10,10,{mv},1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(head)
            def fmt(s): h,r=divmod(s,3600); m,s=divmod(r,60); return f"{int(h)}:{int(m):02d}:{s:05.2f}"
            
            if eff_key == 'fx_scatter':
                for w in words:
                    rx, ry = random.randint(width//4, width*3//4), random.randint(height//4, height*3//4)
                    f.write(f"Dialogue: 0,{fmt(w['start'])},{fmt(w['end'])},Default,,0,0,0,,{{\\an5\\move({rx},{ry},{rx},{ry})\\fad(100,100)}}{w['text']}\n")
                return

            for i, w in enumerate(words):
                st, en = fmt(w['start']), fmt(w['end'])
                
                if eff_key == 'fx_hormozi':
                    f.write(f"Dialogue: 0,{st},{en},Default,,0,0,0,,{{\\an5\\pos({width//2},{height//2})\\fscx120\\fscy120\\1c{c_act}}}{w['text']}\n")
                    continue

                # --- CORRECCIÓN MATEMÁTICA AQUÍ ---
                sel_vis = self.v_vis.get()
                t = TRANSLATIONS[self.lang]
                
                if sel_vis == t['single']:
                    # 1 Palabra (Solo la actual)
                    s_idx = i
                    e_idx = i + 1
                elif sel_vis == t['compact']:
                    # 4 Palabras (1 antes, 1 actual, 2 después)
                    s_idx = max(0, i - 1)
                    e_idx = min(len(words), i + 3)
                elif sel_vis == t['full']:
                    # 11 Palabras (5 antes, 1 actual, 5 después)
                    s_idx = max(0, i - 5)
                    e_idx = min(len(words), i + 6)
                else: 
                    # Balanceado (7 Palabras: 3 antes, 1 actual, 3 después)
                    s_idx = max(0, i - 3)
                    e_idx = min(len(words), i + 4)

                vis = words[s_idx:e_idx]
                # ----------------------------------

                line = ""
                pos_tag = ""
                if pos == 'alternating':
                    alt = (i // 4) % 3
                    if alt == 0: pos_tag = f"{{\\an2\\pos({width//2},{height-50})}}"
                    elif alt == 1: pos_tag = f"{{\\an8\\pos({width//2},50)}}"
                    else: pos_tag = f"{{\\an5\\pos({width//2},{height//2})}}"
                
                if eff_key == 'fx_heart':
                    f.write(f"Dialogue: 1,{st},{en},Default,,0,0,0,,{{\\an5\\pos({width//2},{ty-sz-20})\\1c&H0000FF&}}❤\n")

                for vw in vis:
                    if vw == w:
                        if eff_key == 'fx_pop': line += f"{{\\fscx50\\fscy50\\t(0,100,\\fscx120\\fscy120)\\1c{c_act}}}{vw['text']} "
                        elif eff_key == 'fx_shake': line += f"{{\\t(0,50,\\frz5)\\t(50,100,\\frz-5)\\t(100,150,\\frz0)\\1c{c_act}}}{vw['text']} "
                        elif eff_key == 'fx_glitch': line += f"{{\\t(0,50,\\fscx110\\3c&H0000FF&)\\t(50,100,\\fscx100\\3c&H000000&)\\1c{c_act}}}{vw['text']} "
                        elif eff_key == 'fx_slide': line += f"{{\\move({width//2},{ty+50},{width//2},{ty})\\1c{c_act}}}{vw['text']} "
                        elif eff_key == 'fx_neon': line += f"{{\\bord5\\3c{c_act}\\blur3\\1c&HFFFFFF&}}{vw['text']} "
                        elif eff_key == 'fx_type': line += f"{{\\alpha&H00&}}{vw['text']} "
                        elif eff_key == 'fx_wipe': line += f"{{\\kf{int((w['end']-w['start'])*100)} \\1c{c_act}}}{vw['text']} "
                        elif eff_key == 'fx_bounce': line += f"{{\\t(0,150,\\fscy150)\\t(150,300,\\fscy100)\\1c{c_act}}}{vw['text']} "
                        elif eff_key == 'fx_fade': line += f"{{\\fad(100,100)\\1c{c_act}}}{vw['text']} "
                        elif eff_key == 'fx_pulse': line += f"{{\\t(0,100,\\fscx110\\fscy110)\\t(100,200,\\fscx100\\fscy100)\\1c{c_act}}}{vw['text']} "
                        elif eff_key == 'fx_zoom': line += f"{{\\t(0,100,\\fscx130\\fscy130)\\1c{c_act}}}{vw['text']} "
                        else: line += f"{{\\1c{c_act}}}{vw['text']} "
                    else:
                        line += f"{{\\1c{c_in}}}{vw['text']} "
                f.write(f"Dialogue: 0,{st},{en},Default,,0,0,0,,{pos_tag}{line}\n")

if __name__ == "__main__":
    root = tk.Tk()
    app = KaraokeGenerator(root)
    root.mainloop()
