# VINX0V0Z para Android

Esta APK abre la aplicación Flask de Termux dentro de un WebView nativo. No abre Chrome.

## Uso

1. Ejecuta el backend Flask en un servidor accesible desde Internet o en tu propia máquina:

   `python app.py`

2. Instala la APK en el mismo teléfono o emulador.
3. Abre VINX0V0Z y la app cargará la URL del backend configurada en la compilación.

La app usa `BACKEND_URL` para conectar con el backend.

Para una versión remota, define la URL antes de compilar:

```bash
./gradlew assembleDebug -PBACKEND_URL="https://tu-servidor.example.com"
```

o exporta la variable de entorno:

```bash
export BACKEND_URL="https://tu-servidor.example.com"
./gradlew assembleDebug
```

Si no se define ninguna URL, la app usa un valor de ejemplo: `https://example.com`.

## Compilación

Desde esta carpeta, con Android SDK configurado:

`gradle assembleDebug`

La APK se genera en `app/build/outputs/apk/debug/app-debug.apk`.

Para generar una versión de distribución sin firmar:

`gradle assembleRelease`

La firma de publicación debe configurarse con una clave privada propia antes
de subir el AAB a Google Play.