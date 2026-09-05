# Progreso de VINX0V0Z

## Estado actual

- Backend Flask en `app.py` con generación de voz, traducción, scraper, carga de PDF/TXT/DOCX e historial SQLite.
- Proyecto Android en `android/` con WebView nativo y selector de archivos.
- La APK actual carga `http://127.0.0.1:5000`.
- El backend se puede desplegar con `gunicorn app:app` usando el `Procfile`.
- El SDK Android local está configurado en `android/local.properties`.

## Artefactos generados

- APK debug: `android/app/build/outputs/apk/debug/app-debug.apk`
- Android App Bundle debug: `android/app/build/outputs/bundle/debug/app-debug.aab`

Comando de compilación desde `android/`:

```text
gradle assembleDebug bundleDebug
```

## Para usarlo ahora

1. Iniciar el backend con `python app.py`.
2. Instalar `app-debug.apk` en el mismo teléfono.
3. Abrir VINX0V0Z; la aplicación se conecta a `127.0.0.1:5000`.

## Pendiente para una aplicación independiente

1. Desplegar Flask en Render, Railway u otro proveedor con HTTPS.
2. Cambiar la URL de `MainActivity.java` por la URL pública del backend.
3. Generar una clave de firma y compilar una versión `release` para Google Play.

No se han creado ni guardado claves privadas de firma.
