import os
import re
import uuid
import asyncio
import subprocess
import requests
import json
import zipfile
import sqlite3
import shutil
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import edge_tts

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1GB

ALLOWED_EXTENSIONS = {"mp3", "wav", "ogg", "m4a", "mp4", "webm", "mov", "avi", "srt", "vtt", "txt", "jpg", "png", "jpeg"}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
DATABASE_PATH = os.path.join(BASE_DIR, "vinx0voz.db")

def inicializar_base_datos():
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS producciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                archivo TEXT NOT NULL UNIQUE,
                tipo TEXT NOT NULL DEFAULT 'audio',
                creado_en TEXT NOT NULL
            )
        """)

def registrar_produccion(nombre: str, archivo: str, tipo: str = "audio"):
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute(
            "INSERT OR REPLACE INTO producciones(nombre, archivo, tipo, creado_en) VALUES (?, ?, ?, ?)",
            (nombre, archivo, tipo, datetime.now(timezone.utc).isoformat())
        )

inicializar_base_datos()

# --- INTERFAZ MAESTRA PRO (TRANSFORMA TXT VOZ) ---
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VINX0V0Z - Voice Studio</title>
    <style>
        :root {
            --bg-color: #0a0c10;
            --card-bg: #12151c;
            --accent-color: #bb86fc;
            --accent-hover: #9965f4;
            --text-primary: #e1e4e8;
            --text-secondary: #8b949e;
            --border-color: #2d333b;
            --gold: #ffb74d;
        }
        body {
            font-family: 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            margin: 0; padding: 0;
            display: flex; flex-direction: column;
            height: 100vh; overflow: hidden;
        }
        header { text-align: center; padding: 8px; border-bottom: 1px solid var(--border-color); background: var(--card-bg); }
        h1 { margin: 0; color: var(--accent-color); font-size: 1.4rem; letter-spacing: 2px; }
        .subtitle { font-size: 0.75rem; color: var(--gold); margin-top: 2px; }

        .main-layout { display: flex; flex: 1; overflow: hidden; flex-direction: column; }
        
        .editor-section { flex: 1; display: flex; flex-direction: column; padding: 8px; background: var(--bg-color); }
        .editor-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
        .editor-header span { font-weight: bold; color: var(--accent-color); font-size: 0.85rem; }
        
        textarea {
            flex: 1; width: 100%; background: #010409; border: 1px solid var(--border-color);
            color: #fff; padding: 12px; border-radius: 8px; font-size: 1.1rem; line-height: 1.4; resize: none; outline: none;
        }

        .tools-area { background: var(--card-bg); border-top: 1px solid var(--border-color); max-height: 60%; overflow-y: auto; }
        .accordion { border-bottom: 1px solid var(--border-color); }
        .accordion-btn {
            width: 100%; padding: 12px 15px; background: none; border: none; color: var(--text-primary);
            text-align: left; font-weight: bold; display: flex; justify-content: space-between; cursor: pointer;
        }
        .panel { padding: 0 15px; display: none; background: #0d1117; padding-bottom: 15px; }
        .panel.active { display: block; }

        .master-player { padding: 8px; background: #000; text-align: center; border-bottom: 1px solid var(--border-color); }
        #masterMedia { max-width: 100%; max-height: 180px; display: none; border-radius: 4px; }
        #masterAudio { width: 100%; margin-top: 4px; }

        .btn {
            background: var(--accent-color); color: #000; border: none; padding: 10px;
            border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 8px; width: 100%;
        }
        .btn-secondary { background: #30363d; color: #fff; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }

        input, select { width: 100%; padding: 8px; background: #010409; border: 1px solid var(--border-color); color: #fff; border-radius: 4px; margin-top: 5px; box-sizing: border-box; }
        label { display: block; margin-top: 8px; font-size: 0.75rem; color: var(--text-secondary); }

        .lib-item { display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid var(--border-color); cursor: pointer; align-items: center; }
        .lib-item:hover { background: rgba(255,255,255,0.05); }
        .lib-item span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 70%; }
        .download-link { color: var(--accent-color); text-decoration: none; font-weight: bold; padding: 5px 10px; border: 1px solid; border-radius: 4px; font-size: 0.7rem; }
    </style>
</head>
<body>
    <header>
        <h1>VINX0V0Z</h1>
        <div class="subtitle">Voice Studio</div>
    </header>

    <div class="master-player">
        <video id="masterMedia" controls></video>
        <audio id="masterAudio" controls></audio>
    </div>

    <div class="main-layout">
        <section class="editor-section">
            <div class="editor-header">
                <span>TRANSFORMA TXT VOZ</span>
                <small id="charCount" style="color:var(--text-secondary)">0 chars</small>
            </div>
            <textarea id="mainText" placeholder="Pega aquí guiones, libros o textos infinitos..."></textarea>
            <button class="btn" onclick="procesarVozInfinita()">🚀 PROCESAR Y ESCUCHAR</button>
        </section>

        <div class="tools-area">
            <div class="accordion">
                <button class="accordion-btn" onclick="togglePanel('panelVoces')">🗣️ Catálogo de Voces <span>+</span></button>
                <div id="panelVoces" class="panel">
                    <select id="langFilter" onchange="filtrarVoces()">
                        <option value="es">Español (Principal)</option>
                        <option value="en">Inglés</option>
                        <option value="all">Todas las Voces</option>
                    </select>
                    <select id="voiceSelect"></select>
                    <div class="grid-2">
                        <div><label>Velocidad:</label><input type="range" id="rate" min="-50" max="50" value="0"></div>
                        <div><label>Tono:</label><input type="range" id="pitch" min="-20" max="20" value="0"></div>
                    </div>
                </div>
            </div>

            <div class="accordion">
                <button class="accordion-btn" onclick="togglePanel('panelFX')">🎚️ Estudio & Masterización <span>+</span></button>
                <div id="panelFX" class="panel">
                    <div class="grid-2">
                        <button class="btn btn-secondary" onclick="applyPreset('radio')">📻 Locutor</button>
                        <button class="btn btn-secondary" onclick="applyPreset('pro')">💎 Voz Pro</button>
                        <button class="btn btn-secondary" onclick="applyPreset('eco')">🏟️ Eco</button>
                        <button class="btn btn-secondary" onclick="resetFX()">🔄 Limpio</button>
                    </div>
                    <label>Ecualización personalizada:</label>
                    <input type="range" id="eqLow" min="-12" max="12" value="0" oninput="updateFX()"><small>Bajos</small>
                    <input type="range" id="eqHigh" min="-12" max="12" value="0" oninput="updateFX()"><small>Brillo</small>
                </div>
            </div>

            <div class="accordion">
                <button class="accordion-btn" onclick="togglePanel('panelVideo')">🎥 Creador de Video <span>+</span></button>
                <div id="panelVideo" class="panel">
                    <label>Imágenes/Videos locales:</label>
                    <input type="file" id="mediaFiles" multiple accept="image/*,video/*">
                    <button class="btn btn-secondary" onclick="crearVideoSequence()">🎬 Unir con Audio de Voz</button>
                </div>
            </div>

            <div class="accordion">
                <button class="accordion-btn" onclick="togglePanel('panelLib')">📂 Historial de Producciones <span>+</span></button>
                <div id="panelLib" class="panel">
                    <button class="btn btn-secondary" style="background:#4a148c" onclick="vaciarApp()">🗑️ Limpiar Caché App</button>
                    <div id="libList" style="margin-top:10px;"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        let source, lowNode, highNode, compNode, reverbNode;
        let currentAudioFile = "";

        function initAudioFX() {
            const player = document.getElementById('masterAudio');
            if (source) return;
            source = audioCtx.createMediaElementSource(player);
            lowNode = audioCtx.createBiquadFilter(); lowNode.type = 'lowshelf';
            highNode = audioCtx.createBiquadFilter(); highNode.type = 'highshelf';
            compNode = audioCtx.createDynamicsCompressor();
            source.connect(lowNode); lowNode.connect(highNode); highNode.connect(compNode); compNode.connect(audioCtx.destination);
        }

        function updateFX() {
            initAudioFX();
            lowNode.frequency.value = 250; lowNode.gain.value = document.getElementById('eqLow').value;
            highNode.frequency.value = 3500; highNode.gain.value = document.getElementById('eqHigh').value;
        }

        function applyPreset(p) {
            initAudioFX(); resetFX();
            if(p==='radio') { lowNode.gain.value = 8; compNode.threshold.value = -30; compNode.ratio.value = 12; }
            if(p==='pro') { lowNode.gain.value = 4; highNode.gain.value = 6; compNode.threshold.value = -15; }
            if(p==='eco') { /* Reverb simple se puede emular con delay pero por espacio lo dejamos en EQ */ lowNode.gain.value = -5; highNode.gain.value = 8; }
            updateFX();
        }

        function resetFX() { 
            document.getElementById('eqLow').value = 0; document.getElementById('eqHigh').value = 0; 
            if(compNode) { compNode.threshold.value = -10; compNode.ratio.value = 3; }
            updateFX(); 
        }

        function togglePanel(id) {
            document.querySelectorAll('.panel').forEach(p => { if(p.id !== id) p.classList.remove('active'); });
            document.getElementById(id).classList.toggle('active');
        }

        async function cargarVoces() {
            const res = await fetch('/api/voices');
            window.voces = await res.json();
            filtrarVoces();
        }

        function filtrarVoces() {
            const f = document.getElementById('langFilter').value;
            const s = document.getElementById('voiceSelect');
            s.innerHTML = '';
            window.voces.forEach(v => {
                if(f === 'all' || v.Name.startsWith(f)) {
                    const o = document.createElement('option'); o.value = v.Name;
                    o.innerText = `${v.Name.split('-')[1]} - ${v.Name.split('-')[2]} (${v.Gender === 'Female' ? '♀' : '♂'})`;
                    if(v.Name.includes('Dalia')) o.selected = true;
                    s.appendChild(o);
                }
            });
        }

        async function procesarVozInfinita() {
            const text = document.getElementById('mainText').value;
            const voice = document.getElementById('voiceSelect').value;
            const rate = document.getElementById('rate').value;
            const pitch = document.getElementById('pitch').value;
            if(!text) return alert('Escribe algo.');
            
            const btn = event.target; btn.disabled = true; btn.innerText = '⌛ CONVIRTIENDO...';
            try {
                const res = await fetch('/api/tts/infinite', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text, voice, rate, pitch})
                });
                const d = await res.json();
                if(d.status === 'ok') {
                    currentAudioFile = d.filename;
                    const audio = document.getElementById('masterAudio');
                    audio.src = d.url; audio.play();
                    cargarBiblioteca();
                }
            } finally { btn.disabled = false; btn.innerText = '🚀 PROCESAR Y ESCUCHAR'; }
        }

        async function crearVideoSequence() {
            if(!currentAudioFile) return alert('Genera un audio de voz primero.');
            const files = document.getElementById('mediaFiles').files;
            if(files.length === 0) return alert('Sube fotos o videos.');
            
            const btn = event.target; btn.disabled = true; btn.innerText = '⌛ CREANDO...';
            const formData = new FormData();
            formData.append('audio', currentAudioFile);
            for(let f of files) formData.append('media', f);

            try {
                const res = await fetch('/api/media/sequence', { method: 'POST', body: formData });
                const d = await res.json();
                if(d.status === 'ok') {
                    const video = document.getElementById('masterMedia');
                    video.src = d.url; video.style.display = 'block'; video.play();
                    cargarBiblioteca();
                }
            } finally { btn.disabled = false; btn.innerText = '🎬 Unir con Audio de Voz'; }
        }

        async function cargarBiblioteca() {
            const res = await fetch('/api/biblioteca');
            const d = await res.json();
            const box = document.getElementById('libList'); box.innerHTML = '';
            d.items.forEach(i => {
                const div = document.createElement('div'); div.className = 'lib-item';
                const isVideo = i.archivo.endsWith('.mp4');
                div.innerHTML = `<span>${isVideo ? '🎥' : '🎵'} ${i.archivo}</span> <a href="${i.url}" download class="download-link">Bajar</a>`;
                div.onclick = (e) => { 
                    if(e.target.tagName === 'A') return;
                    if(isVideo) {
                        const v = document.getElementById('masterMedia'); v.src = i.url; v.style.display = 'block'; v.play();
                    } else {
                        const a = document.getElementById('masterAudio'); a.src = i.url; a.play();
                    }
                };
                box.appendChild(div);
            });
        }

        async function vaciarApp() {
            if(confirm('¿Borrar historial de la app?')) { await fetch('/api/limpiar', {method: 'POST'}); cargarBiblioteca(); }
        }

        document.getElementById('mainText').oninput = e => { document.getElementById('charCount').innerText = e.target.value.length + ' chars'; };
        cargarVoces(); cargarBiblioteca();
    </script>
</body>
</html>
"""

# --- BACKEND MULTIMEDIA ---

def split_text(text, limit=3500):
    # Divide por puntos seguidos de espacio para no romper frases
    sentences = re.split(r'(?<=\\.) ', text)
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) < limit:
            current += s
        else:
            chunks.append(current.strip())
            current = s
    if current: chunks.append(current.strip())
    return [c for c in chunks if c]

@app.route('/api/voices')
def get_voices():
    try:
        proc = subprocess.run(["edge-tts", "--list-voices"], capture_output=True, text=True)
        voices = []
        for line in proc.stdout.strip().split('\\n')[2:]:
            parts = re.split(r'\\s{2,}', line)
            if len(parts) >= 2: voices.append({"Name": parts[0], "Gender": parts[1]})
        return jsonify(voices)
    except:
        return jsonify([{"Name": "es-MX-DaliaNeural", "Gender": "Female"}])

@app.route('/api/tts/infinite', methods=['POST'])
def infinite_tts():
    data = request.json
    text = data.get("text", "")
    voice = data.get("voice", "es-MX-DaliaNeural")
    rate = f"{int(data.get('rate', 0)):+}%"
    pitch = f"{int(data.get('pitch', 0)):+}Hz"
    
    id_p = uuid.uuid4().hex[:6]
    chunks = split_text(text)
    
    files = []
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        for i, c in enumerate(chunks):
            p = os.path.join(DOWNLOAD_DIR, f"t_{id_p}_{i}.mp3")
            async def run(txt, v, r, pi, path):
                await edge_tts.Communicate(txt, v, rate=r, pitch=pi).save(path)
            loop.run_until_complete(run(c, voice, rate, pitch, p))
            files.append(p)
        
        final = f"Vinx_Audio_{id_p}.mp3"
        f_path = os.path.join(DOWNLOAD_DIR, final)
        lst = os.path.join(DOWNLOAD_DIR, f"l_{id_p}.txt")
        with open(lst, "w") as f:
            for fp in files: f.write(f"file \'{os.path.abspath(fp)}\'\\n")
        
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", f_path], check=True)
        os.remove(lst)
        for fp in files: os.remove(fp)
        registrar_produccion(final, final, "audio")
        return jsonify({"status": "ok", "url": f"/download/{final}", "filename": final})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
    finally:
        loop.close()

@app.route('/api/media/sequence', methods=['POST'])
def sequence_media():
    audio_file = request.form.get("audio")
    media_files = request.files.getlist("media")
    if not audio_file or not media_files: return jsonify({"status": "error", "error": "Faltan archivos"}), 400
    
    id_p = uuid.uuid4().hex[:6]
    audio_path = os.path.join(DOWNLOAD_DIR, audio_file)
    
    temp_paths = []
    for m in media_files:
        p = os.path.join(DOWNLOAD_DIR, f"m_{id_p}_{secure_filename(m.filename)}")
        m.save(p)
        temp_paths.append(p)
        
    try:
        output = f"Vinx_Video_{id_p}.mp4"
        out_path = os.path.join(DOWNLOAD_DIR, output)
        
        # Slideshow de imágenes si son varias, o video con audio
        if temp_paths[0].lower().endswith(('.jpg', '.png', '.jpeg')):
            # Crear slideshow: 3 segundos por imagen
            lst_img = os.path.join(DOWNLOAD_DIR, f"img_{id_p}.txt")
            with open(lst_img, "w") as f:
                for tp in temp_paths: f.write(f"file \'{os.path.abspath(tp)}\'\\nduration 3\\n")
            
            subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst_img, "-i", audio_path, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out_path], check=True)
            os.remove(lst_img)
        else:
            # Primer video con el audio generado
            subprocess.run(["ffmpeg", "-y", "-i", temp_paths[0], "-i", audio_path, "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest", out_path], check=True)
            
        registrar_produccion(output, output, "video")
        return jsonify({"status": "ok", "url": f"/download/{output}"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
    finally:
        for p in temp_paths: 
            if os.path.exists(p): os.remove(p)

@app.route('/api/limpiar', methods=['POST'])
def limpiar():
    for f in os.listdir(DOWNLOAD_DIR): os.remove(os.path.join(DOWNLOAD_DIR, f))
    with sqlite3.connect(DATABASE_PATH) as db: db.execute("DELETE FROM producciones")
    return jsonify({"status": "ok"})

@app.route("/api/biblioteca")
def biblioteca():
    with sqlite3.connect(DATABASE_PATH) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT archivo FROM producciones ORDER BY id DESC").fetchall()
    return jsonify({"status": "ok", "items": [{"archivo": r["archivo"], "url": f"/download/{r['archivo']}"} for r in rows]})

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route("/download/<path:filename>")
def download(filename): return send_from_directory(DOWNLOAD_DIR, secure_filename(filename))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
