import os
import asyncio
import sqlite3
import re
from datetime import datetime
from flask import Flask, render_template_string, request, send_from_directory, redirect, url_for, jsonify
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import edge_tts
from pypdf import PdfReader
from docx import Document

app = Flask(__name__)
DOWNLOAD_FOLDER = os.path.expanduser("~/downloads") if os.path.exists(os.path.expanduser("~/downloads")) else os.getcwd()
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

DB_PATH = "vinx0voz.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text_preview TEXT,
            voice TEXT,
            filename TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

VOICES = {
    "es-MX-DaliaNeural": "🇲🇽 Dalia (México) - Femenina",
    "es-MX-JorgeNeural": "🇲🇽 Jorge (México) - Masculino",
    "es-ES-AlvaroNeural": "🇪🇸 Álvaro (España) - Masculino",
    "es-ES-ElviraNeural": "🇪🇸 Elvira (España) - Femenina",
    "es-AR-ElenaNeural": "🇦🇷 Elena (Argentina) - Femenina",
    "es-CO-SalomeNeural": "🇨🇴 Salomé (Colombia) - Femenina",
    "es-US-AlonsoNeural": "🇺🇸 Alonso (EE.UU.) - Masculino",
    "en-US-JennyNeural": "🇺🇸 Jenny (Inglés US) - Femenina",
    "en-US-GuyNeural": "🇺🇸 Guy (Inglés US) - Masculino",
    "en-GB-SoniaNeural": "🇬🇧 Sonia (Inglés UK) - Femenina",
    "pt-BR-FranciscaNeural": "🇧🇷 Francisca (Portugués BR)",
    "fr-FR-DeniseNeural": "🇫🇷 Denise (Francés)",
    "de-DE-KatjaNeural": "🇩🇪 Katja (Alemán)",
    "it-IT-DiegoNeural": "🇮🇹 Diego (Italiano)",
    "ja-JP-NanamiNeural": "🇯🇵 Nanami (Japonés)",
    "zh-CN-XiaoxiaoNeural": "🇨🇳 Xiaoxiao (Chino Mandarín)"
}

def smart_text_cleaner(text, is_code_mode):
    if not text:
        return ""
    if is_code_mode:
        text = text.replace("{", " abre llave ").replace("}", " cierra llave ")
        text = text.replace("[", " abre corchete ").replace("]", " cierra corchete ")
        text = text.replace(";", " punto y coma. ").replace("//", " comentario: ")
        text = text.replace("def ", " definición de función ").replace("print(", " mostrar en pantalla ")
    
    lines = text.split('\n')
    cleaned_lines = []
    junk_phrases = ["cookie", "aceptar", "privacidad", "publicidad", "suscríbete", "todos los derechos reservados", "menu", "iniciar sesión"]
    for line in lines:
        line_clean = line.strip()
        if len(line_clean) > 2 and not any(junk in line_clean.lower() for junk in junk_phrases):
            cleaned_lines.append(line_clean)
            
    processed_text = " ".join(cleaned_lines)
    processed_text = re.sub(r'\s+', ' ', processed_text)
    return processed_text.strip()

def generate_smart_filename(text):
    clean_words = re.findall(r'\w+', text.lower())
    keyword = "audio"
    if len(clean_words) >= 2:
        keyword = f"{clean_words[0]}_{clean_words[1]}"
    elif len(clean_words) == 1:
        keyword = clean_words[0]
    unique_hash = os.urandom(3).hex()
    return f"vinx_{keyword[:15]}_{unique_hash}.mp3"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VINX0V0Z - Multimedia & Voice Studio</title>
    <!-- Configuración PWA para instalar como App Nativa -->
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#0b0f19">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <style>
        :root { --bg: #0b0f19; --card: #1e293b; --accent: #8b5cf6; --txt: #f8fafc; --success: #22c55e; --danger: #ef4444; --orange: #f97316; }
        body { background: var(--bg); color: var(--txt); font-family: system-ui, sans-serif; padding: 1rem; margin:0; }
        .container { max-width: 950px; margin: 0 auto; }
        .card { background: var(--card); padding: 1.5rem; border-radius: 14px; margin-bottom: 1.5rem; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.4); border: 1px solid #334155; }
        h1, h2 { color: #a78bfa; margin-top: 0; }
        label { display: block; margin: 0.8rem 0 0.3rem; font-weight: bold; font-size: 0.9rem; color: #cbd5e1; }
        textarea, select, input { width: 100%; padding: 0.8rem; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: white; box-sizing: border-box; }
        .btn { background: var(--accent); color: white; border: none; padding: 0.8rem 1.2rem; border-radius: 8px; cursor: pointer; font-weight: bold; margin-top: 1rem; display: inline-block; text-decoration: none; text-align: center; transition: 0.2s;}
        .btn:hover { opacity: 0.85; transform: translateY(-1px); }
        .btn-orange { background: var(--orange); }
        .btn-green { background: var(--success); }
        .btn-red { background: var(--danger); padding: 0.4rem 0.8rem; font-size: 0.8rem; margin: 0; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }
        .media-player-box { background: #0f172a; border: 2px solid var(--success); padding: 1.2rem; border-radius: 12px; margin-top: 1rem; }
        audio { width: 100%; margin-top: 0.8rem; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5)); }
        .file-item { background: #0f172a; padding: 0.9rem; border-radius: 8px; margin-bottom: 0.6rem; display: flex; justify-content: space-between; align-items: center; border-left: 5px solid var(--accent); }
        .checkbox-container { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.8rem; }
        .checkbox-container input { width: auto; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ VINX0V0Z - Multimedia & Voice Studio</h1>

        <!-- BUSCADOR DE HISTORIAL -->
        <div class="card" style="padding: 1rem;">
            <form method="GET" action="/" style="display: flex; gap: 0.5rem;">
                <input type="text" name="q" value="{{ search_query or '' }}" placeholder="🔍 Buscar en producciones anteriores..." style="margin:0;">
                <button type="submit" class="btn" style="margin:0; padding: 0.5rem 1.2rem;">Buscar</button>
                {% if search_query %}
                <a href="/" class="btn btn-red" style="margin:0; display:flex; align-items:center;">Limpiar</a>
                {% endif %}
            </form>
        </div>

        <!-- SCRAPER Y SUBIDA DE DOCUMENTOS -->
        <div class="grid">
            <div class="card">
                <h2>🌐 Web Scraper</h2>
                <form method="POST" action="/scrape">
                    <input type="url" name="url" placeholder="https://ejemplo.com/articulo" required>
                    <button type="submit" class="btn btn-orange">🔍 Extraer y Limpiar Web</button>
                </form>
            </div>
            <div class="card">
                <h2>📄 Cargar Documento</h2>
                <form method="POST" action="/upload_doc" enctype="multipart/form-data">
                    <input type="file" name="document" accept=".pdf,.txt,.docx" required style="padding: 0.4rem;">
                    <button type="submit" class="btn btn-green">📂 Procesar Archivo</button>
                </form>
            </div>
        </div>

        <!-- CONSOLA PRINCIPAL -->
        <div class="card">
            <h2>🎛️ Consola de Producción con Auto-Limpieza</h2>
            <form method="POST" action="/generate">
                <label>Texto, Guion o Código Masivo:</label>
                <textarea name="text" rows="6" placeholder="Pega tu texto aquí. VINX0V0Z eliminará automáticamente anuncios y repeticiones...">{{ last_text or "" }}</textarea>

                <div class="checkbox-container">
                    <input type="checkbox" id="code_mode" name="code_mode" value="yes">
                    <label for="code_mode" style="margin:0; cursor:pointer;">💻 Modo Código / Técnico (Optimizar símbolos)</label>
                </div>

                <div class="grid-3" style="margin-top: 1rem;">
                    <div>
                        <label>🌐 Traducción Global:</label>
                        <select name="target_lang">
                            <option value="none">Mantener original</option>
                            <option value="es">Español</option>
                            <option value="en">Inglés</option>
                            <option value="pt">Portugués</option>
                            <option value="fr">Francés</option>
                        </select>
                    </div>
                    <div>
                        <label>🗣️ Voces e Idiomas:</label>
                        <select name="voice">
                            {% for code, name in voices.items() %}
                            <option value="{{ code }}">{{ name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div>
                        <label>⚡ Velocidad:</label>
                        <select name="rate">
                            <option value="+0%">Normal (1:1)</option>
                            <option value="+20%">Rápida (+20%)</option>
                            <option value="+50%">Turbo (+50%)</option>
                            <option value="-20%">Lenta (-20%)</option>
                        </select>
                    </div>
                </div>

                <button type="submit" class="btn" style="width:100%; font-size: 1.1rem; margin-top: 1.5rem;">🚀 Limpiar, Procesar y Generar Audio</button>
            </form>
        </div>

        <!-- REPRODUCTOR MULTIMEDIA AVANZADO -->
        {% if last_audio %}
        <div class="media-player-box">
            <h2>🎧 Reproductor Multimedia - Última Producción</h2>
            <p style="color: #cbd5e1; font-size: 0.9rem;">Audio generado y guardado automáticamente en tu dispositivo:</p>
            <audio controls controlsList="download" src="{{ url_for('download_file', filename=last_audio) }}"></audio>
            <div style="margin-top: 1rem; display: flex; gap: 1rem;">
                <a href="{{ url_for('download_file', filename=last_audio) }}" class="btn btn-green" style="margin:0;" download>📥 Descargar MP3 Maestro</a>
            </div>
        </div>
        {% endif %}

        <!-- BIBLIOTECA E HISTORIAL -->
        <div class="card" style="margin-top: 1.5rem;">
            <h2>📁 Biblioteca de Producciones (VINX0V0Z Archive)</h2>
            {% if history %}
                {% for item in history %}
                <div class="file-item">
                    <div>
                        <strong>🎵 {{ item[3] }}</strong> <small style="color: #94a3b8;">({{ item[4] }})</small><br>
                        <span style="font-size: 0.85rem; color: #94a3b8;">Texto: "{{ item[1][:50] }}..."</span>
                    </div>
                    <div style="display: flex; gap: 0.5rem; align-items: center;">
                        <a href="{{ url_for('download_file', filename=item[3]) }}" class="btn" style="padding: 0.4rem 0.8rem; margin:0;" target="_blank">Reproducir</a>
                        <a href="{{ url_for('delete_item', item_id=item[0]) }}" class="btn btn-red">Borrar</a>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <p style="color: #64748b;">No hay producciones guardadas todavía.</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

# Ruta automática para el manifiesto de la aplicación móvil (PWA)
@app.route("/manifest.json")
def manifest():
    return jsonify({
        "name": "VINX0V0Z - Multimedia & Voice Studio",
        "short_name": "VINX0V0Z",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0b0f19",
        "theme_color": "#0b0f19",
        "icons": [
            {
                "src": "https://img.icons8.com/fluency/96/lightning-bolt.png",
                "sizes": "96x96",
                "type": "image/png"
            }
        ]
    })

def get_history(search_query=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if search_query:
        cursor.execute("SELECT * FROM history WHERE text_preview LIKE ? OR filename LIKE ? ORDER BY id DESC", 
                       (f"%{search_query}%", f"%{search_query}%"))
    else:
        cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT 15")
    history = cursor.fetchall()
    conn.close()
    return history

@app.route("/")
def index():
    search_query = request.args.get("q", "")
    return render_template_string(HTML_TEMPLATE, voices=VOICES, history=get_history(search_query), last_text="", last_audio=None, search_query=search_query)

@app.route("/scrape", methods=["POST"])
def scrape():
    url = request.form.get("url")
    extracted_text = ""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.decompose()
        paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3'])
        raw_text = "\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
        extracted_text = smart_text_cleaner(raw_text, False)
    except Exception as e:
        extracted_text = f"Error al extraer la URL: {str(e)}"

    return render_template_string(HTML_TEMPLATE, voices=VOICES, history=get_history(), last_text=extracted_text, last_audio=None, search_query="")

@app.route("/upload_doc", methods=["POST"])
def upload_doc():
    extracted_text = ""
    if 'document' in request.files:
        file = request.files['document']
        filename = file.filename.lower()
        raw_text = ""
        if filename.endswith('.pdf'):
            try:
                reader = PdfReader(file)
                for page in reader.pages:
                    text = page.extract_text()
                    if text: raw_text += text + "\n"
            except Exception as e: raw_text = f"Error leyendo PDF: {e}"
        elif filename.endswith('.txt'):
            raw_text = file.read().decode('utf-8', errors='ignore')
        elif filename.endswith('.docx'):
            try:
                doc = Document(file)
                raw_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
            except Exception as e: raw_text = f"Error leyendo Word: {e}"
        
        extracted_text = smart_text_cleaner(raw_text, False)

    return render_template_string(HTML_TEMPLATE, voices=VOICES, history=get_history(), last_text=extracted_text, last_audio=None, search_query="")

async def generate_tts(text, voice, rate, output_path):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)

@app.route("/generate", methods=["POST"])
def generate():
    text = request.form.get("text")
    voice = request.form.get("voice")
    target_lang = request.form.get("target_lang")
    rate = request.form.get("rate", "+0%")
    is_code_mode = True if request.form.get("code_mode") else False

    if not text:
        return redirect(url_for('index'))

    cleaned_text = smart_text_cleaner(text, is_code_mode)

    if target_lang != "none":
        try:
            cleaned_text = GoogleTranslator(source='auto', target=target_lang).translate(cleaned_text)
        except Exception as e:
            print(f"Error en traducción: {e}")

    filename = generate_smart_filename(cleaned_text)
    output_path = os.path.join(DOWNLOAD_FOLDER, filename)

    asyncio.run(generate_tts(cleaned_text, voice, rate, output_path))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO history (text_preview, voice, filename, created_at) VALUES (?, ?, ?, ?)",
                   (cleaned_text[:150], voice, filename, now))
    conn.commit()
    conn.close()

    return render_template_string(HTML_TEMPLATE, voices=VOICES, history=get_history(), last_text=cleaned_text, last_audio=filename, search_query="")

@app.route("/delete/<int:item_id>")
def delete_item(item_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT filename FROM history WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    if row:
        filename = row[0]
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        cursor.execute("DELETE FROM history WHERE id = ?", (item_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route("/downloads/<filename>")
def download_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

