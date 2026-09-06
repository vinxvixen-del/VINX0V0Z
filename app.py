import os
import re
import uuid
import asyncio
import subprocess
import sqlite3
import shutil
import zipfile
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

# --- INTERFAZ UNIQUE EDITION (ESTUDIO PREMIUM) ---
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VINX0V0Z - Unique Studio</title>
    <style>
        :root {
            --bg: #05070a;
            --card: rgba(22, 27, 34, 0.8);
            --accent: #bb86fc;
            --gold: #ffb74d;
            --text: #e1e4e8;
            --border: #30363d;
        }
        body {
            font-family: 'Inter', system-ui, sans-serif;
            background: var(--bg);
            background-image: radial-gradient(circle at top right, #1a1b26, transparent);
            color: var(--text);
            margin: 0; padding: 15px;
            box-sizing: border-box;
            min-height: 100vh;
        }
        header {
            text-align: center;
            margin-bottom: 20px;
        }
        h1 { margin: 0; color: var(--accent); font-size: 2.2rem; text-transform: uppercase; letter-spacing: 4px; }
        .subtitle { color: var(--gold); font-size: 0.9rem; font-weight: bold; }

        .dashboard {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1300px;
            margin: 0 auto;
        }
        @media(max-width: 900px) { .dashboard { grid-template-columns: 1fr; } }

        .card {
            background: var(--card);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        }
        .card h3 {
            margin-top: 0;
            color: var(--accent);
            font-size: 1.1rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px;
            display: flex;
            justify-content: space-between;
        }

        /* EDITOR GIGANTE */
        .editor-container {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        textarea {
            width: 100%;
            height: 450px;
            background: #010409;
            border: 1px solid var(--border);
            color: #fff;
            padding: 15px;
            border-radius: 12px;
            font-size: 1.15rem;
            line-height: 1.6;
            resize: none;
            outline: none;
            box-sizing: border-box;
        }
        textarea:focus { border-color: var(--accent); box-shadow: 0 0 10px rgba(187, 134, 252, 0.2); }

        /* CONTROLES */
        label { display: block; margin-top: 15px; font-size: 0.85rem; color: var(--gold); font-weight: bold; }
        select, input[type="text"], input[type="file"] {
            width: 100%;
            padding: 12px;
            background: #0d1117;
            border: 1px solid var(--border);
            color: #fff;
            border-radius: 8px;
            margin-top: 5px;
            box-sizing: border-box;
        }

        .btn {
            background: var(--accent);
            color: #000;
            border: none;
            padding: 14px;
            border-radius: 8px;
            font-weight: bold;
            cursor: pointer;
            width: 100%;
            margin-top: 15px;
            transition: transform 0.2s, background 0.2s;
            text-transform: uppercase;
        }
        .btn:hover { background: #9965f4; transform: translateY(-2px); }
        .btn:active { transform: translateY(0); }
        
        .btn-green { background: #238636; color: #fff; }
        .btn-blue { background: #1f6feb; color: #fff; }
        .btn-orange { background: #d97706; color: #fff; }

        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }

        /* REPRODUCTORES */
        .player-box {
            background: #000;
            border-radius: 12px;
            padding: 10px;
            margin-top: 10px;
            border: 1px solid var(--border);
        }
        audio, video { width: 100%; }
        video { max-height: 250px; border-radius: 8px; }

        /* BIBLIOTECA */
        .library {
            margin-top: 20px;
            max-height: 200px;
            overflow-y: auto;
            background: #010409;
            border-radius: 8px;
            border: 1px solid var(--border);
        }
        .lib-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            border-bottom: 1px solid var(--border);
        }
        .lib-item:last-child { border: none; }
        .lib-item a { color: var(--accent); text-decoration: none; font-size: 0.8rem; border: 1px solid; padding: 4px 8px; border-radius: 4px; }
    </style>
</head>
<body>
    <header>
        <h1>VINX0V0Z</h1>
        <div class="subtitle">Unique Voice Studio</div>
    </header>

    <div class="dashboard">
        <!-- COLUMNA IZQUIERDA: EDITOR -->
        <div class="card">
            <h3>✍️ TXTVOZ <small id="charCount">0 chars</small></h3>
            <div class="editor-container">
                <textarea id="textoInput" placeholder="Escribe o pega aquí tu guión masivo..."></textarea>
                <button class="btn" onclick="sintetizarVoz()">🚀 Transformar a Audio Pro</button>
            </div>
        </div>

        <!-- COLUMNA DERECHA: ESTUDIO -->
        <div class="card">
            <h3>🎙️ Configuración de Estudio</h3>
            
            <label>Seleccionar Voz:</label>
            <select id="vozSelect">
                <option value="es-MX-DaliaNeural">Dalia (México ♀)</option>
                <option value="es-MX-JorgeNeural">Jorge (México ♂)</option>
                <option value="es-ES-AlvaroNeural">Álvaro (España ♂)</option>
                <option value="es-ES-ElviraNeural">Elvira (España ♀)</option>
                <option value="en-US-AndrewNeural">Andrew (USA ♂)</option>
                <option value="en-US-JennyNeural">Jenny (USA ♀)</option>
                <option value="pt-BR-AntonioNeural">Antonio (Brasil ♂)</option>
            </select>

            <div class="grid-2">
                <div><label>Velocidad:</label><input type="range" id="rateRange" min="-50" max="50" value="0" style="width:100%"></div>
                <div><label>Tono:</label><input type="range" id="pitchRange" min="-20" max="20" value="0" style="width:100%"></div>
            </div>

            <label>Reproductor de Audio:</label>
            <div class="player-box">
                <audio id="audioPlayer" controls></audio>
            </div>

            <label>Cargar Multimedia Local:</label>
            <input type="file" id="mediaFile" accept="audio/*,video/*,image/*">
            
            <div class="grid-2">
                <button class="btn btn-green" onclick="subirArchivo()">⬆️ Cargar</button>
                <button class="btn btn-blue" onclick="generarVideo()">🎥 Crear Video</button>
            </div>
            
            <button class="btn btn-orange" onclick="exportarPaquete()">📦 Exportar Paquete ZIP</button>

            <label>Visor de Video:</label>
            <div class="player-box">
                <video id="mainVideo" controls></video>
            </div>
        </div>
    </div>

    <!-- BIBLIOTECA INFERIOR -->
    <div class="card" style="max-width:1300px; margin: 20px auto;">
        <h3>📂 Biblioteca de Producciones <button class="btn btn-orange" style="width:auto; margin:0; padding:5px 15px; font-size:0.7rem;" onclick="vaciarApp()">Limpiar App</button></h3>
        <div class="library" id="libraryBox">
            <div style="padding:20px; text-align:center; color:var(--border);">Cargando producciones...</div>
        </div>
    </div>

    <script>
        let ultimoArchivo = '';

        async function sintetizarVoz() {
            const texto = document.getElementById('textoInput').value;
            const voz = document.getElementById('vozSelect').value;
            const rate = document.getElementById('rateRange').value;
            const pitch = document.getElementById('pitchRange').value;
            if (!texto) return alert('El campo de texto está vacío.');

            const btn = event.target;
            btn.innerText = '⌛ Procesando...'; btn.disabled = true;

            try {
                const res = await fetch('/api/tts/sintetizar', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({texto, voz, rate, pitch})
                });
                const data = await res.json();
                if(data.status === 'ok') {
                    const audio = document.getElementById('audioPlayer');
                    audio.src = data.audio_url; audio.play();
                    ultimoArchivo = data.filename;
                    cargarBiblioteca();
                } else { alert('Error: ' + data.error); }
            } catch(e) { alert('Error de conexión.'); }
            finally { btn.innerText = '🚀 Transformar a Audio Pro'; btn.disabled = false; }
        }

        async function subirArchivo() {
            const file = document.getElementById('mediaFile').files[0];
            if (!file) return alert('Selecciona un archivo.');
            const formData = new FormData();
            formData.append('archivo', file);
            try {
                const res = await fetch('/api/media/upload', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.status === 'ok') {
                    ultimoArchivo = data.filename;
                    alert('Cargado: ' + data.filename);
                    cargarBiblioteca();
                }
            } catch (e) { alert('Error al subir.'); }
        }

        async function generarVideo() {
            if (!ultimoArchivo) return alert('Genera un audio primero.');
            const btn = event.target; btn.innerText = '⌛ Creando...'; btn.disabled = true;
            try {
                const res = await fetch('/api/media/video', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({audio: ultimoArchivo})
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    const video = document.getElementById('mainVideo');
                    video.src = data.video_url; video.play();
                    cargarBiblioteca();
                }
            } finally { btn.innerText = '🎥 Crear Video'; btn.disabled = false; }
        }

        async function exportarPaquete() {
            if (!ultimoArchivo) return alert('No hay producción seleccionada.');
            try {
                const res = await fetch('/api/exportar/zip', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({filename: ultimoArchivo})
                });
                const data = await res.json();
                if (data.status === 'ok') { window.location.href = data.download_url; }
            } catch (e) { alert('Error al exportar.'); }
        }

        async function cargarBiblioteca() {
            const res = await fetch('/api/biblioteca');
            const data = await res.json();
            const box = document.getElementById('libraryBox');
            box.innerHTML = '';
            if(data.items.length === 0) box.innerHTML = '<div style="padding:20px; text-align:center;">Sin producciones.</div>';
            data.items.forEach(i => {
                const div = document.createElement('div');
                div.className = 'lib-item';
                div.innerHTML = `<span>${i.archivo}</span> <a href="${i.url}" download>BAJAR</a>`;
                div.onclick = (e) => {
                    if(e.target.tagName === 'A') return;
                    ultimoArchivo = i.archivo;
                    if(i.archivo.endsWith('.mp4')) {
                        const v = document.getElementById('mainVideo'); v.src = i.url; v.play();
                    } else {
                        const a = document.getElementById('audioPlayer'); a.src = i.url; a.play();
                    }
                };
                box.appendChild(div);
            });
        }

        async function vaciarApp() {
            if(confirm('¿Borrar historial?')) { await fetch('/api/limpiar', {method: 'POST'}); cargarBiblioteca(); }
        }

        document.getElementById('textoInput').addEventListener('input', e => {
            document.getElementById('charCount').innerText = e.target.value.length + ' chars';
        });

        cargarBiblioteca();
    </script>
</body>
</html>
"""

# --- BACKEND MULTIMEDIA ---

def segmentar_texto(texto, limite=3500):
    fragmentos = []
    actual = ""
    for frase in re.split(r'(?<=\\.) ', texto):
        if len(actual) + len(frase) < limite:
            actual += frase
        else:
            fragmentos.append(actual.strip())
            actual = frase
    if actual: fragmentos.append(actual.strip())
    return [f for f in fragmentos if f]

@app.route("/api/tts/sintetizar", methods=["POST"])
def api_sintetizar():
    try:
        data = request.json
        texto = data.get("texto", "").strip()
        voz = data.get("voz", "es-MX-DaliaNeural")
        rate = f"{int(data.get('rate', 0)):+}%"
        pitch = f"{int(data.get('pitch', 0)):+}Hz"
        
        if not texto: return jsonify({"status": "error", "error": "Texto vacío"}), 400
        
        id_p = uuid.uuid4().hex[:6]
        fragmentos = segmentar_texto(texto)
        files = []
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            for i, frag in enumerate(fragmentos):
                p = os.path.join(DOWNLOAD_DIR, f"temp_{id_p}_{i}.mp3")
                async def run_tts():
                    await edge_tts.Communicate(frag, voz, rate=rate, pitch=pitch).save(p)
                loop.run_until_complete(run_tts())
                files.append(p)
            
            final_name = f"Vinx_Audio_{id_p}.mp3"
            final_path = os.path.join(DOWNLOAD_DIR, final_name)
            
            if len(files) > 1:
                lst = os.path.join(DOWNLOAD_DIR, f"list_{id_p}.txt")
                with open(lst, "w") as f:
                    for fp in files: f.write(f"file \'{os.path.abspath(fp)}\'\\n")
                subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", final_path], check=True)
                os.remove(lst)
                for fp in files: os.remove(fp)
            else:
                os.rename(files[0], final_path)
                
            registrar_produccion(final_name, final_name, "audio")
            return jsonify({"status": "ok", "audio_url": f"/download/{final_name}", "filename": final_name})
        finally:
            loop.close()
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/media/upload", methods=["POST"])
def api_media_upload():
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename: return jsonify({"status": "error", "error": "Sin archivo"}), 400
    nombre = secure_filename(archivo.filename)
    destino = os.path.join(DOWNLOAD_DIR, nombre)
    archivo.save(destino)
    registrar_produccion(nombre, nombre, "video" if nombre.endswith(('.mp4', '.mov', '.avi')) else "audio")
    return jsonify({"status": "ok", "filename": nombre, "url": f"/download/{nombre}"})

@app.route("/api/media/video", methods=["POST"])
def api_generar_video():
    try:
        audio = request.json.get("audio")
        audio_path = os.path.join(DOWNLOAD_DIR, audio)
        id_p = uuid.uuid4().hex[:6]
        output = f"Vinx_Video_{id_p}.mp4"
        out_path = os.path.join(DOWNLOAD_DIR, output)
        
        # Generar video con fondo negro y audio
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30",
            "-i", audio_path, "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-movflags", "+faststart", out_path
        ], check=True)
        
        registrar_produccion(output, output, "video")
        return jsonify({"status": "ok", "video_url": f"/download/{output}", "filename": output})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/biblioteca")
def api_biblioteca():
    with sqlite3.connect(DATABASE_PATH) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT archivo FROM producciones ORDER BY id DESC").fetchall()
    return jsonify({"status": "ok", "items": [{"archivo": r["archivo"], "url": f"/download/{r['archivo']}"} for r in rows]})

@app.route('/api/limpiar', methods=['POST'])
def api_limpiar():
    for f in os.listdir(DOWNLOAD_DIR): 
        try: os.remove(os.path.join(DOWNLOAD_DIR, f))
        except: pass
    with sqlite3.connect(DATABASE_PATH) as db: db.execute("DELETE FROM producciones")
    return jsonify({"status": "ok"})

@app.route("/api/exportar/zip", methods=["POST"])
def api_exportar_zip():
    try:
        filename = request.json.get("filename")
        path = os.path.join(DOWNLOAD_DIR, filename)
        zip_name = f"Pack_{filename}.zip"
        zip_path = os.path.join(DOWNLOAD_DIR, zip_name)
        with zipfile.ZipFile(zip_path, "w") as z:
            z.write(path, arcname=filename)
        return jsonify({"status": "ok", "download_url": f"/download/{zip_name}"})
    except: return jsonify({"status": "error"}), 500

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route("/download/<path:filename>")
def download(filename): return send_from_directory(DOWNLOAD_DIR, secure_filename(filename))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
