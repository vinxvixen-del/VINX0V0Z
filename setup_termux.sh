#!/bin/bash

echo "🚀 Iniciando configuración de VINX0V0Z en Termux..."

# Actualizar paquetes
echo "📦 Actualizando paquetes del sistema..."
pkg update -y && pkg upgrade -y

# Instalar dependencias del sistema
echo "🛠️ Instalando Python y FFmpeg..."
pkg install -y python ffmpeg

# Crear entorno virtual si no existe (opcional pero recomendado)
if [ ! -d "venv" ]; then
    echo "🌐 Creando entorno virtual Python..."
    python -m venv venv
fi

# Activar entorno e instalar requerimientos
source venv/bin/activate
echo "🐍 Instalando librerías de Python..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Configuración completada."
echo "▶️ Para iniciar el servidor usa: source venv/bin/activate && python app.py"
python app.py
