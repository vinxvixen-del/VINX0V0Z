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
import importlib
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename
import edge_tts
try:
    genai = importlib.import_module("google.generativeai")
except ImportError:
    genai = None

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "mp3", "wav", "ogg", "m4a", "mp4", "webm",
    "mov", "avi", "srt", "vtt", "txt"
}

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

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY and genai is not None:
    genai.configure(api_key=GEMINI_API_KEY)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")

# --- INTERFAZ MAESTRA POTENCIADA Y UNIFICADA (VINX0V0Z PRO) ---
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VINX0V0Z - Multimedia & Voice Studio Pro</title>
    <style>
        :root {
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --accent-color: #8b5cf6;
            --accent-hover: #7c3aed;
            --text-color: #c9d1d9;
            --border-color: #30363d;
            --gold-color: #f59e0b;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            text-align: center;
            margin-bottom: 25px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 15px;
        }
        h1 {
            color: #a78bfa;
            font-size: 2.2rem;
            margin: 0;
        }
        .subtitle {
            color: var(--gold-color);
            font-size: 0.9rem;
            margin-top: 5px;
        }
        .grid-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        @media(max-width: 768px) {
            .grid-container { grid-template-columns: 1fr; }
        }
        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            margin-bottom: 20px;
        }
        .card h3 {
            margin-top: 0;
            color: #c084fc;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
        }
        label {
            display: block;
            margin-top: 12px;
            font-weight: 600;
            font-size: 0.85rem;
            color: #d2d6dc;
        }
        input, select, textarea {
            width: 100%;
            padding: 10px;
            margin-top: 5px;
            background-color: #010409;
            border: 1px solid var(--border-color);
            color: var(--text-color);
            border-radius: 6px;
            box-sizing: border-box;
        }
        textarea {
            resize: vertical;
            height: 100px;
        }
        button {
            background-color: var(--accent-color);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            width: 100%;
            margin-top: 15px;
            transition: background 0.2s;
        }
        button:hover {
            background-color: var(--accent-hover);
        }
        .mic-btn {
            background-color: #2d1b4e;
            border: 1px solid #a855f7;
            color: #e9d5ff;
            margin-bottom: 10px;
        }
        .media-player-box {
            background: #000;
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            margin-top: 10px;
            border: 1px solid var(--border-color);
        }
        video, audio {
            width: 100%;
            border-radius: 6px;
            outline: none;
        }
        .speed-controls {
            display: flex;
            gap: 5px;
            margin-top: 10px;
        }
        .speed-btn {
            background-color: #21262d;
            border: 1px solid var(--border-color);
            color: var(--text-color);
            padding: 6px;
            font-size: 0.8rem;
            cursor: pointer;
            border-radius: 4px;
            flex: 1;
            margin-top: 0;
        }
        .speed-btn:hover {
            background-color: #30363d;
        }
        .karaoke-screen {
            background: #010409;
            border: 1px dashed var(--accent-color);
            border-radius: 6px;
            padding: 12px;
            min-height: 60px;
            max-height: 120px;
            overflow-y: auto;
            font-family: monospace;
            color: #d8b4fe;
            margin-top: 10px;
            font-size: 0.9rem;
        }
        .karaoke-screen span.active {
            color: var(--gold-color);
            background: rgba(245, 158, 11, 0.2);
            font-weight: bold;
            padding: 2px 4px;
            border-radius: 3px;
        }
        .library-list {
            max-height: 150px;
            overflow-y: auto;
            background: #010409;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 8px;
            font-size: 0.85rem;
        }
        .library-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px;
            border-bottom: 1px solid #21262d;
        }
        .library-item a {
            color: #a78bfa;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>⚡ VINX0V0Z</h1>
            <div class="subtitle">Multimedia & Voice Studio Pro • Motor Híbrido IA & Producción Masiva</div>
        </header>

        <div class="grid-container">
            <!-- COLUMNA IZQUIERDA: IA, MICRÓFONO Y ESTUDIO DE VOZ -->
            <div>
                <div class="card">
                    <h3>🤖 Asistente IA & Generador de Guiones</h3>
                    <label>Idea o Prompt para Letra/Guion/Podcast:</label>
                    <textarea id="promptIa" rows="2" placeholder="Ej: Estructura una letra de Trap en 90 BPM..."></textarea>
                    <button type="button" onclick="generarGuion()">✨ Generar Contenido con IA</button>
                </div>

                <div class="card">
                    <h3>🎙️ Consola de Producción y Voz</h3>
                    <button type="button" class="mic-btn" id="micBtn" onclick="toggleMic()">🎙️ Dictar por Micrófono (Voz a Texto)</button>
                    
                    <label>Texto, Guión o Script Masivo:</label>
                    <textarea id="textoInput" placeholder="Escribe, pega texto o genera contenido con IA..."></textarea>
                    
                    <label>Título de la Producción (Archivo):</label>
                    <input type="text" id="nombreArchivo" value="produccion_vinx_01">

                    <label>Catálogo Global de Voces e Idiomas:</label>
                    <select id="vozSelect">
                        <option value="es-MX-DaliaNeural">Dalia (México - Femenina)</option>
                        <option value="es-MX-JorgeNeural">Jorge (México - Masculino)</option>
                        <option value="es-ES-AlvaroNeural">Álvaro (España - Masculino)</option>
                        <option value="es-ES-ElviraNeural">Elvira (España - Femenina)</option>
                        <option value="es-AR-TomasNeural">Tomás (Argentina - Masculino)</option>
                        <option value="es-CO-SalomeNeural">Salomé (Colombia - Femenina)</option>
                        <option value="en-US-AndrewNeural">Andrew (USA - Masculino)</option>
                        <option value="en-US-JennyNeural">Jenny (USA - Femenina)</option>
                        <option value="fr-FR-HenriNeural">Henri (Francia - Francés)</option>
                        <option value="ja-JP-NanamiNeural">Nanami (Japón - Japonés)</option>
                        <option value="de-DE-KillianNeural">Killian (Alemania - Alemán)</option>
                        <option value="it-IT-DiegoNeural">Diego (Italia - Italiano)</option>
                        <option value="pt-BR-AntonioNeural">Antonio (Brasil - Portugués)</option>
                    </select>

                    <div style="display: flex; gap: 10px;">
                        <div style="flex:1;">
                            <label>Velocidad (%):</label>
                            <input type="range" id="rateRange" min="-50" max="50" value="0">
                        </div>
                        <div style="flex:1;">
                            <label>Tono (Hz):</label>
                            <input type="range" id="pitchRange" min="-20" max="20" value="0">
                        </div>
                    </div>

                    <button type="button" onclick="sintetizarVoz()">🚀 Limpiar, Procesar y Generar Audio</button>
                </div>
            </div>

            <!-- COLUMNA DERECHA: KARAOKE, REPRODUCTOR Y HERRAMIENTAS AVANZADAS -->
            <div>
                <div class="card">
                    <h3>👁️ Visor de Audio y Texto (Karaoke Vivo & SRT)</h3>
                    <div class="karaoke-screen" id="karaokeBox">Esperando síntesis de audio...</div>

                    <label style="margin-top: 15px;">Reproductor Principal HD</label>
                    <div class="media-player-box">
                        <audio id="audioPlayer" controls></audio>
                        <div class="speed-controls">
                            <button class="speed-btn" onclick="setSpeed(0.5)">0.5x</button>
                            <button class="speed-btn" onclick="setSpeed(1.0)">1.0x</button>
                            <button class="speed-btn" onclick="setSpeed(1.5)">1.5x</button>
                            <button class="speed-btn" onclick="setSpeed(2.0)">2.0x</button>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <h3>🎬 Reproductor Multimedia & Edición Avanzada</h3>
                    <div class="media-player-box">
                        <video id="mainVideo" controls>
                            <source src="" type="video/mp4">
                        </video>
                    </div>

                    <label style="margin-top: 12px;">Cargar Archivo Multimedia (Audio/Video/Docs):</label>
                    <input type="file" id="mediaFile">
                    
                    <button type="button" style="background-color: #238636;" onclick="subirArchivo()">⬆️ Cargar Archivo Multimedia</button>
                    <button type="button" style="background-color: #238636;" onclick="separarStems()">🎧 Separar Audio / Reducir Ruido</button>
                    <button type="button" style="background-color: #1f6feb;" onclick="generarVideo()">🎥 Generar Video Temático / Subtítulos</button>
                    <button type="button" style="background-color: #d97706;" onclick="exportarPaquete()">📦 Exportar Paquete ZIP de Distribución</button>
                </div>

                <div class="card">
                    <h3>📂 Biblioteca de Producciones (Historial Local)</h3>
                    <div class="library-list" id="libraryBox">
                        <div class="library-item"><span>Sin producciones recientes.</span></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let recognition; let isRecording = false; let ultimoArchivo = '';
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.lang = 'es-MX'; recognition.continuous = true; recognition.interimResults = true;
            recognition.onresult = (e) => {
                let t = '';
                for (let i = e.resultIndex; i < e.results.length; i++) { t += e.results[i][0].transcript; }
                document.getElementById('textoInput').value = t;
            };
        }
        function toggleMic() {
            if (!recognition) return alert('Micrófono no soportado en este navegador.');
            const btn = document.getElementById('micBtn');
            if (!isRecording) { recognition.start(); isRecording = true; btn.innerText = '🔴 Grabando Voz...'; btn.style.background = '#831843'; }
            else { recognition.stop(); isRecording = false; btn.innerText = '🎙️ Dictar por Micrófono'; btn.style.background = '#2d1b4e'; }
        }

        function setSpeed(rate) {
            const audio = document.getElementById('audioPlayer');
            const video = document.getElementById('mainVideo');
            audio.playbackRate = rate;
            video.playbackRate = rate;
        }

        async function subirArchivo() {
            const archivo = document.getElementById('mediaFile').files[0];
            if (!archivo) return alert('Selecciona un archivo.');

            const datos = new FormData();
            datos.append('archivo', archivo);

            try {
                const respuesta = await fetch('/api/media/upload', {
                    method: 'POST',
                    body: datos
                });
                const resultado = await respuesta.json();

                if (resultado.status !== 'ok') {
                    return alert(resultado.error || 'No se pudo cargar el archivo.');
                }

                ultimoArchivo = resultado.filename;

                if (archivo.type.startsWith('video/')) {
                    const video = document.getElementById('mainVideo');
                    video.src = resultado.url;
                    video.load();
                } else if (archivo.type.startsWith('audio/')) {
                    const audio = document.getElementById('audioPlayer');
                    audio.src = resultado.url;
                    audio.load();
                }

                alert('Archivo cargado correctamente.');
            } catch (error) {
                alert('Error de conexión al cargar el archivo.');
            }
        }

        async function generarGuion() {
            const prompt = document.getElementById('promptIa').value;
            if (!prompt) return alert('Ingresa una idea.');
            try {
                const res = await fetch('/api/ia/generar', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({prompt, proveedor: 'gemini'}) });
                const data = await res.json();
                if(data.status === 'ok') { document.getElementById('textoInput').value = data.texto; }
                else { alert('Error de IA: ' + (data.error || 'Desconocido')); }
            } catch(e) { alert('Error conectando con el servidor de IA.'); }
        }

        async function sintetizarVoz() {
            const texto = document.getElementById('textoInput').value;
            const voz = document.getElementById('vozSelect').value;
            const rate = parseInt(document.getElementById('rateRange').value);
            const pitch = parseInt(document.getElementById('pitchRange').value);
            const filename = document.getElementById('nombreArchivo').value || 'audio_salida';
            if (!texto) return alert('El campo de texto está vacío.');

                   android/.gradle/
            android/build/
            android/app/build/
            try {
                const res = await fetch('/api/tts/sintetizar', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({texto, voz, rate, pitch, filename}) });
                const data = await res.json();
                if(data.status === 'ok') {
                    const audioPlayer = document.getElementById('audioPlayer');
                    audioPlayer.src = data.audio_url; audioPlayer.play();
                    ultimoArchivo = data.filename;
                    iniciarKaraokeVisual(texto);
                    actualizarBiblioteca(filename, data.audio_url);
                } else {
                    alert('Error en síntesis: ' + (data.error || 'No se pudo generar'));
                }
            } catch(e) { alert('Error de conexión al procesar el audio.'); }
        }


        async function exportarPaquete() {
            if (!ultimoArchivo) return alert('Genera o carga primero una producción.');
            try {
                const respuesta = await fetch('/api/exportar/zip', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({filename: ultimoArchivo})
                });
                const resultado = await respuesta.json();
                if (resultado.status !== 'ok') return alert(resultado.error || 'No se pudo exportar el paquete.');
                const enlace = document.createElement('a');
                enlace.href = resultado.download_url;
                enlace.download = resultado.filename;
                enlace.click();
            } catch (error) {
                alert('Error de conexión al exportar el paquete.');
            }
        }
        async function separarStems() {
            if (!ultimoArchivo) return alert('Genera primero un audio.');
            const respuesta = await fetch('/api/media/stems', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({audio: ultimoArchivo})
            });
            const resultado = await respuesta.json();
            if (resultado.status !== 'ok') return alert(resultado.error);
            alert(resultado.nota || 'Procesamiento completado.');
        }

        async function generarVideo() {
            if (!ultimoArchivo) return alert('Genera primero un audio.');
            const respuesta = await fetch('/api/media/video', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({audio: ultimoArchivo})
            });
            const resultado = await respuesta.json();
            if (resultado.status !== 'ok') return alert(resultado.error);
            const video = document.getElementById('mainVideo');
            video.src = resultado.video_url;
            video.load();
            alert('Vídeo generado correctamente.');
        }

        async function cargarBiblioteca() {
            const respuesta = await fetch('/api/biblioteca');
            const resultado = await respuesta.json();
            if (resultado.status !== 'ok' || !resultado.items.length) return;
            const biblioteca = document.getElementById('libraryBox');
            biblioteca.innerHTML = '';
            resultado.items.forEach(item => {
                const fila = document.createElement('div');
                fila.className = 'library-item';
                fila.innerHTML = `<span>🎵 ${item.archivo}</span><a href="${item.url}" download>📥 Descargar</a>`;
                biblioteca.appendChild(fila);
            });
        }

        cargarBiblioteca().catch(() => {});
        function iniciarKaraokeVisual(textoCompleto) {
            const box = document.getElementById('karaokeBox');
            const palabras = textoCompleto.split(' '); let index = 0; box.innerHTML = '';
            palabras.forEach((p, i) => {
                const span = document.createElement('span'); span.id = 'w_' + i; span.innerText = p + ' '; box.appendChild(span);
            });
            const audio = document.getElementById('audioPlayer');
            const interval = setInterval(() => {
                if (audio.paused) return;
                const prev = document.getElementById('w_' + (index - 1)); if(prev) prev.classList.remove('active');
                const curr = document.getElementById('w_' + index);
                if(curr) { curr.classList.add('active'); curr.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); index++; }
                else { clearInterval(interval); }
            }, 300);
        }

        function actualizarBiblioteca(nombre, url) {
            const lib = document.getElementById('libraryBox');
            if(lib.innerHTML.includes('Sin producciones')) lib.innerHTML = '';
            const item = document.createElement('div');
            item.className = 'library-item';
            item.innerHTML = `<span>🎵 ${nombre}.mp3</span> <a href="${url}" download>📥 Descargar</a>`;
            lib.prepend(item);
        }
    </script>
</body>
</html>
"""

# --- MOTORES DE BACKEND ROBUSTOS ---

def fragmentar_texto_extremo(texto: str, max_chars: int = 3500) -> list:
    parrafos = [p.strip() for p in re.split(r'\n+', texto) if len(p.strip()) > 0]
    bloques_finales = []
    for p in parrafos:
        if len(p) <= max_chars:
            bloques_finales.append(p)
        else:
            palabras = p.split(' ')
            bloque_actual = []
            longitud_actual = 0
            for w in palabras:
                if longitud_actual + len(w) + 1 > max_chars:
                    bloques_finales.append(" ".join(bloque_actual))
                    bloque_actual = [w]
                    longitud_actual = len(w)
                else:
                    bloque_actual.append(w)
                    longitud_actual += len(w) + 1
            if bloque_actual:
                bloques_finales.append(" ".join(bloque_actual))
    return bloques_finales

def validar_nombre(nombre: str, extension: str = "mp3") -> str:
    limpio = secure_filename(str(nombre or "produccion_vinx"))
    base = Path(limpio).stem[:80] or "produccion_vinx"
    return f"{base}.{extension}"

def extension_permitida(nombre: str) -> bool:
    return Path(nombre).suffix.lower().lstrip(".") in ALLOWED_EXTENSIONS

def validar_texto(texto: str) -> str:
    texto = str(texto or "").strip()
    if not texto:
        raise ValueError("El texto no puede estar vacío")
    if len(texto) > 1_000_000:
        raise ValueError("El texto supera el límite permitido")
    return texto

def ejecutar_ffmpeg(argumentos: list[str]):
    ejecutable = shutil.which("ffmpeg")
    if not ejecutable:
        try:
            import imageio_ffmpeg
            ejecutable = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            ejecutable = None
    if not ejecutable:
        raise RuntimeError("FFmpeg no está instalado. Instale ffmpeg o imageio-ffmpeg")
    return subprocess.run(
        [ejecutable, "-y", *argumentos],
        capture_output=True,
        text=True,
        check=True
    )

def generar_texto_ia(prompt: str, proveedor: str = "gemini", modelo_local: str = "llama3.2") -> str:
    prompt = validar_texto(prompt)
    if proveedor == "gemini" and GEMINI_API_KEY and genai is not None:
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Fallback Gemini error: {e}")

    try:
        payload = {"model": modelo_local, "prompt": prompt, "stream": False}
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        return resp.json().get("response", "").strip()
    except Exception as e:
        return f"Guion estructurado: {prompt}"

async def sintetizar_bloque(texto: str, voz: str, rate: str, pitch: str, ruta_mp3: str, ruta_srt: str):
    communicator = edge_tts.Communicate(texto, voz, rate=rate, pitch=pitch)
    submaker = edge_tts.SubMaker()

    with open(ruta_mp3, "wb") as file:
        async for chunk in communicator.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)

    srt_data = submaker.get_srt()
    with open(ruta_srt, "w", encoding="utf-8") as f:
        f.write(srt_data if srt_data else "")

def procesar_texto_infinito(texto: str, voz: str, rate: int, pitch: int, filename: str) -> str:
    bloques = fragmentar_texto_extremo(texto)
    archivos_temporales = []

    rate_str = f"{'+' if rate >= 0 else ''}{rate}%"
    pitch_str = f"{'+' if pitch >= 0 else ''}{pitch}Hz"

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        for idx, bloque in enumerate(bloques):
            tmp_audio = os.path.join(DOWNLOAD_DIR, f"tmp_{uuid.uuid4().hex[:6]}_{idx}.mp3")
            tmp_srt = os.path.join(DOWNLOAD_DIR, f"tmp_{uuid.uuid4().hex[:6]}_{idx}.srt")
            loop.run_until_complete(sintetizar_bloque(bloque, voz, rate_str, pitch_str, tmp_audio, tmp_srt))
            archivos_temporales.append(tmp_audio)
    finally:
        loop.close()

    output_mp3 = os.path.join(DOWNLOAD_DIR, f"{filename}.mp3")
    concat_list = os.path.join(DOWNLOAD_DIR, f"list_{uuid.uuid4().hex[:6]}.txt")

    with open(concat_list, "w", encoding="utf-8") as f:
        for audio in archivos_temporales:
            f.write(f"file '{audio}'\n")

    try:
        ejecutar_ffmpeg([
            "-f", "concat", "-safe", "0", "-i", concat_list,
            "-c", "copy", output_mp3
        ])
    finally:
        if os.path.exists(concat_list):
            os.remove(concat_list)
        for tmp in archivos_temporales:
            if os.path.exists(tmp):
                os.remove(tmp)

    registrar_produccion(filename, f"{filename}.mp3", "audio")
    return f"{filename}.mp3"

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/ia/generar", methods=["POST"])
def api_generar():
    try:
        data = request.get_json(silent=True) or {}
        resultado = generar_texto_ia(
            data.get("prompt", ""),
            data.get("proveedor", "gemini"),
            data.get("modelo_local", "llama3.2")
        )
        return jsonify({"status": "ok", "texto": resultado})
    except ValueError as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    except Exception:
        app.logger.exception("Error generando contenido")
        return jsonify({"status": "error", "error": "No se pudo generar el contenido"}), 500

@app.route("/api/tts/sintetizar", methods=["POST"])
def api_sintetizar():
    try:
        data = request.get_json(silent=True) or {}
        texto = validar_texto(data.get("texto"))
        voz = data.get("voz", "es-MX-DaliaNeural")
        rate = max(-50, min(50, int(data.get("rate", 0))))
        pitch = max(-20, min(20, int(data.get("pitch", 0))))
        filename = Path(validar_nombre(
            data.get("filename", f"audio_{uuid.uuid4().hex[:6]}"), "mp3"
        )).stem

        archivo_final = procesar_texto_infinito(texto, voz, rate, pitch, filename)
        return jsonify({
            "status": "ok",
            "filename": archivo_final,
            "audio_url": f"/download/{archivo_final}"
        })
    except ValueError as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    except Exception:
        app.logger.exception("Error sintetizando audio")
        return jsonify({"status": "error", "error": "No se pudo generar el audio"}), 500

@app.route("/api/media/upload", methods=["POST"])
def api_media_upload():
    archivo = request.files.get("archivo")

    if not archivo or not archivo.filename:
        return jsonify({"status": "error", "error": "No se recibió ningún archivo"}), 400

    if not extension_permitida(archivo.filename):
        return jsonify({"status": "error", "error": "Tipo de archivo no permitido"}), 400

    nombre = secure_filename(archivo.filename)
    destino = os.path.join(DOWNLOAD_DIR, nombre)
    archivo.save(destino)
    registrar_produccion(Path(nombre).stem, nombre, "video" if Path(nombre).suffix.lower() in {".mp4", ".webm", ".mov", ".avi"} else "audio")

    return jsonify({
        "status": "ok",
        "filename": nombre,
        "url": f"/download/{nombre}"
    })

@app.route("/api/biblioteca", methods=["GET"])
def api_biblioteca():
    with sqlite3.connect(DATABASE_PATH) as db:
        db.row_factory = sqlite3.Row
        filas = db.execute(
            "SELECT nombre, archivo, tipo, creado_en FROM producciones ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return jsonify({
        "status": "ok",
        "items": [
            {
                "nombre": fila["nombre"],
                "archivo": fila["archivo"],
                "tipo": fila["tipo"],
                "creado_en": fila["creado_en"],
                "url": f"/download/{fila['archivo']}"
            }
            for fila in filas
        ]
    })

@app.route("/api/media/video", methods=["POST"])
def api_generar_video():
    try:
        data = request.get_json(silent=True) or {}
        audio = validar_nombre(data.get("audio"), "mp3")
        ruta_audio = os.path.join(DOWNLOAD_DIR, audio)
        if not os.path.isfile(ruta_audio):
            return jsonify({"status": "error", "error": "No se encontró el audio"}), 404

        base = Path(audio).stem
        video = f"{base}_video.mp4"
        ruta_video = os.path.join(DOWNLOAD_DIR, video)
        ejecutar_ffmpeg([
            "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30",
            "-i", ruta_audio, "-shortest",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-movflags", "+faststart", ruta_video
        ])
        registrar_produccion(base, video, "video")
        return jsonify({
            "status": "ok",
            "filename": video,
            "video_url": f"/download/{video}"
        })
    except RuntimeError as error:
        return jsonify({"status": "error", "error": str(error)}), 503
    except subprocess.CalledProcessError as error:
        app.logger.error("FFmpeg: %s", error.stderr[-1000:])
        return jsonify({"status": "error", "error": "FFmpeg no pudo generar el vídeo"}), 422

@app.route("/api/media/stems", methods=["POST"])
def api_separar_audio():
    try:
        data = request.get_json(silent=True) or {}
        audio = validar_nombre(data.get("audio"), "mp3")
        ruta_audio = os.path.join(DOWNLOAD_DIR, audio)
        if not os.path.isfile(ruta_audio):
            return jsonify({"status": "error", "error": "No se encontró el audio"}), 404

        base = Path(audio).stem
        mono = f"{base}_mono.wav"
        ruta_mono = os.path.join(DOWNLOAD_DIR, mono)
        ejecutar_ffmpeg(["-i", ruta_audio, "-ac", "1", "-ar", "44100", ruta_mono])
        registrar_produccion(base, mono, "audio")
        return jsonify({
            "status": "ok",
            "files": [{"filename": mono, "url": f"/download/{mono}"}],
            "nota": "Separación básica a mono completada. Para stems IA instale Demucs."
        })
    except RuntimeError as error:
        return jsonify({"status": "error", "error": str(error)}), 503
    except subprocess.CalledProcessError:
        return jsonify({"status": "error", "error": "No se pudo procesar el audio"}), 422

@app.route("/api/exportar/zip", methods=["POST"])
def api_exportar_zip():
    try:
        data = request.get_json(silent=True) or {}
        nombre_audio = validar_nombre(data.get("filename"), "mp3")
        ruta_audio = os.path.join(DOWNLOAD_DIR, nombre_audio)

        if not os.path.isfile(ruta_audio):
            return jsonify({
                "status": "error",
                "error": "La producción todavía no existe"
            }), 404

        base = Path(nombre_audio).stem
        nombre_zip = f"{base}_distribucion.zip"
        ruta_zip = os.path.join(DOWNLOAD_DIR, nombre_zip)
        metadatos = {
            "aplicacion": "VINX0V0Z",
            "archivo_audio": nombre_audio,
            "generado_en": datetime.now(timezone.utc).isoformat(),
            "formato": "MP3"
        }

        with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as paquete:
            paquete.write(ruta_audio, arcname=nombre_audio)
            ruta_srt = os.path.join(DOWNLOAD_DIR, f"{base}.srt")
            if os.path.isfile(ruta_srt):
                paquete.write(ruta_srt, arcname=f"{base}.srt")
            paquete.writestr("metadatos.json", json.dumps(metadatos, ensure_ascii=False, indent=2))

        return jsonify({
            "status": "ok",
            "filename": nombre_zip,
            "download_url": f"/download/{nombre_zip}"
        })
    except Exception:
        app.logger.exception("Error exportando paquete ZIP")
        return jsonify({
            "status": "error",
            "error": "No se pudo crear el paquete ZIP"
        }), 500

@app.route("/download/<path:filename>")
def download(filename):
    nombre = secure_filename(filename)
    if nombre != filename or not nombre:
        return jsonify({"status": "error", "error": "Archivo no válido"}), 400

    ruta = os.path.join(DOWNLOAD_DIR, nombre)
    if not os.path.isfile(ruta):
        return jsonify({"status": "error", "error": "Archivo no encontrado"}), 404

    return send_from_directory(DOWNLOAD_DIR, nombre, as_attachment=False)

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1"
    )