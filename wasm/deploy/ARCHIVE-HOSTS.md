# Servidores de archivos

El juego y la landing son públicos; no hay usuario ni contraseña.

`PUBLIC_ARCHIVE_URL` y `MOD_ARCHIVE_URL` son las URLs HTTPS completas de `public.zip`
y `mod.zip`, por ejemplo `https://public.matiusrock.com/` y `https://mod.matiusrock.com/`.
Al iniciar el contenedor se escriben en la página de `/play/`, y el navegador
descarga los ZIP directamente de esas URLs.
Admiten letras, números, `:`, `/`, `.`, `_` y `-`; no parámetros de consulta.
Recrea el contenedor para aplicar cambios de variables.

Los servidores de archivos deben permitir peticiones `Range` y responder con:

- `Access-Control-Allow-Origin` con el origen del juego (`https://play.matiusrock.com`)
- `Access-Control-Expose-Headers: Content-Range, Content-Length, Accept-Ranges`
- `Cross-Origin-Resource-Policy: cross-origin`

Cualquiera que conozca las URLs de los ZIP puede descargarlos mientras sean públicas.
