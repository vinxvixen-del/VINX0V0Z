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

# --- INTERFAZ FUNCTIONAL PRO ---
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VINX0V0Z - Functional Studio</title>
    <style>
        :root {
            --bg: #05070a;
            --card: rgba(22, 27, 34, 0.9);
            --accent: #bb86fc;
            --gold: #ffb74d;
            --text: #e1e4e8;
            --border: #30363d;
            --error: #f85149;
            --success: #238636;
        }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0; padding: 10px;
            display: flex; flex-direction: column;
            height: 100vh; box-sizing: border-box;
            overflow: hidden;
        }
        header { text-align: center; padding: 5px; }
        h1 { margin: 0; color: var(--accent); font-size: 1.6rem; letter-spacing: 3px; }
        .subtitle { color: var(--gold); font-size: 0.8rem; letter-spacing: 1px; }

        .dashboard {
            display: flex; flex: 1; gap: 15px; overflow: hidden;
            margin-top: 10px;
        }
        @media(max-width: 800px) { .dashboard { flex-direction: column; overflow-y: auto; } }

        .column-left { flex: 1.5; display: flex; flex-direction: column; min-width: 0; }
        .column-right { flex: 1; display: flex; flex-direction: column; min-width: 0; gap: 15px; }

        .card {
            background: var(--card); border: 1px solid var(--border);
            border-radius: 12px; padding: 15px; display: flex; flex-direction: column;
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
        }
        .card h3 { margin: 0 0 10px 0; font-size: 1rem; color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 5px; }

        textarea {
            flex: 1; width: 100%; background: #010409; border: 1px solid var(--border);
            color: #fff; padding: 15px; border-radius: 8px; font-size: 1.1rem; line-height: 1.5;
            resize: none; outline: none; box-sizing: border-box; min-height: 300px;
        }
        textarea:focus { border-color: var(--accent); }

        .controls { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
        select, input {
            width: 100%; padding: 10px; background: #0d1117; border: 1px solid var(--border);
            color: #fff; border-radius: 6px; box-sizing: border-box; font-size: 0.9rem;
        }
        label { font-size: 0.75rem; color: var(--gold); margin-top: 8px; display: block; font-weight: bold; }

        .btn {
            background: var(--accent); color: #000; border: none; padding: 12px;
            border-radius: 6px; font-weight: bold; cursor: pointer; width: 100%;
            margin-top: 10px; font-size: 0.9rem; text-transform: uppercase;
        }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-green { background: var(--success); color: #fff; }
        .btn-orange { background: var(--gold); color: #000; }

        .media-container { background: #000; border-radius: 8px; padding: 5px; text-align: center; }
        video { width: 100%; max-height: 180px; border-radius: 4px; display: none; }
        audio { width: 100%; margin-top: 5px; }

        #statusInfo { font-size: 0.8rem; margin-top: 5px; color: var(--gold); text-align: center; height: 1.2rem; }

        .library { flex: 1; overflow-y: auto; background: #010409; border-radius: 6px; border: 1px solid var(--border); }
        .lib-item {
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px 12px; border-bottom: 1px solid var(--border); font-size: 0.85rem; cursor: pointer;
        }
        .lib-item:hover { background: rgba(255,255,255,0.05); }
        .lib-item span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 65%; }
        .actions a { color: var(--accent); text-decoration: none; font-size: 0.75rem; font-weight: bold; }
    </style>
</head>
<body>
    <header>
        <h1>VINX0V0Z</h1>
        <div class="subtitle">Voice & Media Studio Pro</div>
    </header>

    <div id="statusInfo">Listo para trabajar.</div>

    <div class="dashboard">
        <div class="column-left">
            <div class="card" style="flex:1">
                <h3>✍️ CONVERTIDOR TXTVOZ</h3>
                <textarea id="textoInput" placeholder="Escribe o pega aquí textos largos..."></textarea>
                
                <div class="controls">
                    <div>
                        <label>Voz:</label>
                        <select id="vozSelect">
                            <option value="es-MX-DaliaNeural">Dalia (MX ♀)</option>
                            <option value="es-MX-JorgeNeural">Jorge (MX ♂)</option>
                            <option value="es-ES-AlvaroNeural">Alvaro (ES ♂)</option>
                            <option value="es-ES-ElviraNeural">Elvira (ES ♀)</option>
                            <option value="en-US-AndrewNeural">Andrew (US ♂)</option>
                            <option value="en-US-JennyNeural">Jenny (US ♀)</option>
                        </select>
                    </div>
                    <div>
                        <label>Velocidad:</label>
                        <select id="rateSelect">
                            <option value="-20%">Lento</option>
                            <option value="0%" selected>Normal</option>
                            <option value="+20%">Rápido</option>
                            <option value="+50%">Veloz</option>
                        </select>
                    </div>
                </div>
                <button id="btnProcesar" class="btn" onclick="iniciarConversion()">🚀 GENERAR AUDIO COMPLETO</button>
            </div>
        </div>

        <div class="column-right">
            <div class="card">
                <h3>🎬 REPRODUCTOR MAESTRO</h3>
                <div class="media-container">
                    <video id="mainVideo" controls></video>
                    <audio id="mainAudio" controls></audio>
                </div>
                <label>Cargar archivo local (Video/Audio/Imagen):</label>
                <input type="file" id="inputFile" accept="audio/*,video/*,image/*">
                <button class="btn btn-green" onclick="subirYProcesar()">⬆️ CARGAR Y REPRODUCIR</button>
            </div>

            <div class="card" style="flex:1;">
                <h3>📂 HISTORIAL</h3>
                <div class="library" id="libList"></div>
                <button class="btn btn-orange" style="margin-top:10px;" onclick="limpiarTodo()">🗑️ LIMPIAR HISTORIAL</button>
            </div>
        </div>
    </div>

    <script>
        function setStatus(msg, isError = false) {
            const s = document.getElementById('statusInfo');
            s.innerText = msg;
            s.style.color = isError ? 'var(--error)' : 'var(--gold)';
        }

        async function iniciarConversion() {
            const text = document.getElementById('textoInput').value.trim();
            const voice = document.getElementById('vozSelect').value;
            const rate = document.getElementById('rateSelect').value;
            if(!text) return alert('Ingresa un texto.');

            const btn = document.getElementById('btnProcesar');
            btn.disabled = true;
            setStatus("⏳ Procesando... puede tardar varios segundos.");

            try {
                const response = await fetch('/api/tts/pro', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text, voice, rate})
                });
                const data = await response.json();
                
                if(data.status === 'ok') {
                    setStatus("✅ ¡Listo!");
                    document.getElementById('mainAudio').src = data.url;
                    document.getElementById('mainAudio').play();
                    actualizarBiblioteca();
                } else {
                    setStatus("❌ Error: " + data.error, true);
                }
            } catch(e) {
                setStatus("❌ Error de red", true);
            } finally {
                btn.disabled = false;
            }
        }

        async function subirYProcesar() {
            const file = document.getElementById('inputFile').files[0];
            if(!file) return alert("Selecciona un archivo.");
            setStatus("⬆️ Subiendo...");
            const formData = new FormData();
            formData.append('archivo', file);
            try {
                const res = await fetch('/api/upload', { method: 'POST', body: formData });
                const data = await res.json();
                if(data.status === 'ok') {
                    setStatus("✅ Cargado.");
                    const video = document.getElementById('mainVideo');
                    const audio = document.getElementById('mainAudio');
                    if(file.type.startsWith('video/')) {
                        video.src = data.url; video.style.display = 'block'; video.play();
                    } else {
                        video.style.display = 'none'; audio.src = data.url; audio.play();
                    }
                    actualizarBiblioteca();
                }
            } catch(e) { setStatus("❌ Fallo", true); }
        }

        async function actualizarBiblioteca() {
            const res = await fetch('/api/list');
            const data = await res.json();
            const box = document.getElementById('libList');
            box.innerHTML = '';
            data.items.forEach(item => {
                const div = document.createElement('div');
                div.className = 'lib-item';
                div.innerHTML = `<span>${item.name}</span><a href="${item.url}" download>BAJAR</a>`;
                div.onclick = (e) => {
                    if(e.target.tagName === 'A') return;
                    const v = document.getElementById('mainVideo');
                    const a = document.getElementById('mainAudio');
                    if(item.name.endsWith('.mp4')) {
                        v.src = item.url; v.style.display = 'block'; v.play();
                    } else {
                        v.style.display = 'none'; a.src = item.url; a.play();
                    }
                };
                box.appendChild(div);
            });
        }

        async function limpiarTodo() {
            if(!confirm("¿Borrar historial?")) return;
            await fetch('/api/clear', {method: 'POST'});
            actualizarBiblioteca();
        }

        actualizarBiblioteca();
    </script>
</body>
</html>
"""

@app.route('/api/tts/pro', methods=['POST'])
def api_tts_pro():
    try:
        data = request.json
        text = data.get("text", "")
        voice = data.get("voice", "es-MX-DaliaNeural")
        rate = data.get("rate", "0%")
        
        if not text: return jsonify({"status": "error", "error": "Texto vacío"}), 400
        
        # Segmentar por longitud si no hay párrafos claros
        chunks = []
        for p in text.split('\n'):
            p = p.strip()
            if not p: continue
            # Si el párrafo es muy largo, dividirlo por caracteres
            while len(p) > 3000:
                chunks.append(p[:3000])
                p = p[3000:]
            chunks.append(p)
            
        id_job = uuid.uuid4().hex[:6]
        temp_files = []
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            for i, c in enumerate(chunks):
                fpath = os.path.join(DOWNLOAD_DIR, f"p_{id_job}_{i}.mp3")
                async def run_tts():
                    await edge_tts.Communicate(c, voice, rate=rate).save(fpath)
                loop.run_until_complete(run_tts())
                if os.path.exists(fpath): temp_files.append(fpath)
            
            final_name = f"Vinx_Prod_{id_job}.mp3"
            final_path = os.path.join(DOWNLOAD_DIR, final_name)
            
            if len(temp_files) > 1:
                list_path = os.path.join(DOWNLOAD_DIR, f"list_{id_job}.txt")
                with open(list_path, "w", encoding='utf-8') as f:
                    for fp in temp_files:
                        f.write(f"file '{os.path.abspath(fp)}'\\n")
                
                # EJECUCIÓN FFMPEG
                subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", final_path], check=True)
                os.remove(list_path)
                for fp in temp_files: os.remove(fp)
            else:
                os.rename(temp_files[0], final_path)
                
            registrar_produccion(final_name, final_name, "audio")
            return jsonify({"status": "ok", "url": f"/download/{final_name}", "filename": final_name})
        finally:
            loop.close()
            
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def api_upload():
    f = request.files.get('archivo')
    if not f: return jsonify({"status": "error"}), 400
    name = secure_filename(f.filename)
    path = os.path.join(DOWNLOAD_DIR, name)
    f.save(path)
    registrar_produccion(name, name, "video" if name.lower().endswith(('.mp4','.mov')) else "audio")
    return jsonify({"status": "ok", "url": f"/download/{name}"})

@app.route('/api/list')
def api_list():
    with sqlite3.connect(DATABASE_PATH) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT archivo FROM producciones ORDER BY id DESC").fetchall()
    return jsonify({"status": "ok", "items": [{"name": r["archivo"], "url": f"/download/{r['archivo']}"} for r in rows]})

@app.route('/api/clear', methods=['POST'])
def api_clear():
    for f in os.listdir(DOWNLOAD_DIR): 
        try: os.remove(os.path.join(DOWNLOAD_DIR, f))
        except: pass
    with sqlite3.connect(DATABASE_PATH) as db: db.execute("DELETE FROM producciones")
    return jsonify({"status": "ok"})

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route("/download/<path:filename>")
def download(filename): return send_from_directory(DOWNLOAD_DIR, secure_filename(filename))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
