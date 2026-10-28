# Subir los archivos del port de 0 A.D. a Cloudflare R2

Guía para Windows/PowerShell y un despliegue web en CasaOS.
Fecha de consulta de la documentación: 25 de octubre de 2026.

## 1. Qué vas a publicar

La imagen Docker de unos 2 GB y los archivos del juego son cosas diferentes:

- La imagen Docker se ejecuta en CasaOS y se distribuye mediante un registro de
  contenedores o una transferencia local.
- R2 almacena objetos descargables. Aquí subirás `public.zip` y `mod.zip` del
  paquete web compilado, sin descomprimirlos ni volverlos a comprimir.
- La landing, HTML, módulos JavaScript, workers, WASM y manifiestos pueden seguir
  en tu servidor web de CasaOS. El navegador descargará los ZIP directamente de R2.

Subir una imagen Docker exportada a R2 no hace que Cloudflare ejecute el juego.
Tampoco basta con subir los ZIP: hay que conectar el cargador con sus URLs.

En este repositorio ya existen lecturas por bloques con `Range`, comprobación
SHA-256 y persistencia en IndexedDB, en `wasm/browser/archive-blocks.mjs`.
Por eso los 2 GB totales no equivalen necesariamente a una descarga completa
antes de empezar. Las lecturas por bloques sí generan múltiples operaciones R2.

## 2. Preparativos y costo

Necesitas una cuenta Cloudflare con R2 activado, los archivos de una compilación
que hayas elegido y rclone instalado. Cloudflare puede solicitar datos de pago
al activar R2; revisa lo que muestra tu cuenta.

Selecciona **Standard**. Actualmente incluye cada mes 10 GB-mes de almacenamiento,
un millón de operaciones clase A y diez millones de clase B. El excedente cuesta
US$0,015/GB-mes, US$4,50/millón de clase A y US$0,36/millón de clase B.
La transferencia de salida directa de R2 es gratuita. Se aplican redondeos de
facturación; el dominio, impuestos y servicios adicionales se calculan aparte.

Dos GB almacenados pueden quedar en US$0/mes si el resto del uso está dentro de
las cuotas. Las versiones anteriores y otros buckets de la cuenta también consumen
la cuota. Consulta [precios oficiales](https://developers.cloudflare.com/r2/pricing/)
y revisa periódicamente uso y facturación; una alerta no constituye un límite de gasto.

## 3. Crear el bucket

1. Abre el panel de Cloudflare y entra en **R2 Object Storage**.
2. Selecciona **Create bucket**.
3. Usa un nombre, por ejemplo `0ad-web-assets`.
4. En **Location**, deja **Automatic**. Si el panel propone **Eastern North
   America**, es una elección inicial razonable para probar desde Colombia.
   No necesitas completar **Provide a location hint** para empezar.
5. Selecciona almacenamiento **Standard** y crea el bucket.
6. Déjalo privado mientras preparas la carga.

**Location** indica dónde se almacenan los datos del bucket. Automatic elige una
región disponible cercana a quien realiza la petición de creación. Si la mayoría
de tus jugadores estará en otra región, puedes usar **Provide a location hint**
para sugerirla al crear el bucket; es una preferencia, no una garantía de ubicación
ni de mejor latencia. Los jugadores pueden acceder desde otros países.

**Specify jurisdiction** sirve para exigir residencia de datos en una jurisdicción
concreta. Para este despliegue de archivos públicos no hemos identificado esa
necesidad: deja Automatic. Una jurisdicción asignada no se puede cambiar después.
Consulta [ubicación de datos en R2](https://developers.cloudflare.com/r2/reference/data-location/).

Dedica este bucket a contenido que puedas publicar. No subas configuraciones,
credenciales, backups personales ni carpetas completas del repositorio.

Usaremos esta estructura de objetos:

```text
0ad-web-assets/
  releases/
    beta-001/
      public.zip
      mod.zip
```

`beta-001` es una versión de ejemplo. Cada nueva publicación debe tener su propio
prefijo para evitar mezclar bloques, manifiestos y archivos de distintas versiones.

## 4. Crear credenciales de carga

1. En R2, abre la administración de **R2 API tokens**.
2. Crea un token con permiso **Object Read & Write**, limitado al bucket
   `0ad-web-assets`.
3. Guarda el **Access Key ID**, **Secret Access Key** y el endpoint S3 que muestra
   Cloudflare. El secreto puede mostrarse una sola vez.
4. Usa exactamente el endpoint de tu bucket/cuenta, especialmente si elegiste una
   jurisdicción específica. El habitual tiene este formato:

   ```text
   https://ACCOUNT_ID.r2.cloudflarestorage.com
   ```

Estas credenciales son para tu equipo de carga. Nunca deben aparecer en HTML,
JavaScript, Git ni capturas públicas. El endpoint S3 no es la URL pública del juego.

## 5. Instalar y configurar rclone

Descarga rclone desde [su web oficial](https://rclone.org/downloads/), extrae el
ejecutable y agrégalo al PATH, o ejecútalo desde su carpeta como `./rclone.exe`.
Comprueba la instalación:

```powershell
rclone version
rclone config
```

En el asistente selecciona las opciones por su nombre, porque los números pueden cambiar:

1. Nuevo remoto: nombre `r2`.
2. Tipo de almacenamiento: **Amazon S3 Compliant Storage Providers**.
3. Proveedor: **Cloudflare R2**.
4. Credenciales manuales: introduce el Access Key ID y Secret Access Key.
5. Región: `auto`, si la configuración lo solicita.
6. Endpoint: el endpoint S3 que copiaste del panel.
7. Deja las demás opciones en sus valores por defecto, salvo que tu cuenta indique otra cosa.

Si el token limitado al bucket provoca errores de comprobación del bucket, configura
`no_check_bucket = true` para ese remoto. Los comandos de carga de esta guía ya
incluyen la opción equivalente `--s3-no-check-bucket`.

El archivo de configuración de rclone contiene credenciales: mantenlo fuera del
repositorio y protege el acceso al equipo. Puedes usar la opción de cifrado de
configuración de rclone. Consulta la [guía oficial de R2 con rclone](https://developers.cloudflare.com/r2/examples/rclone/).

## 6. Subir los ZIP desde PowerShell

Abre PowerShell en la raíz del repositorio. Sustituye el nombre de paquete del
ejemplo por el directorio de tu compilación elegida; no es un nombre real garantizado.

```powershell
$packagePath = Resolve-Path 'wasm/dist/application-phase4-5-TU-CANDIDATO'
$releaseName = 'beta-001'
$remotePath = "r2:0ad-web-assets/releases/$releaseName"

Get-Item -LiteralPath (Join-Path $packagePath 'public.zip')
Get-Item -LiteralPath (Join-Path $packagePath 'mod.zip')
```

Comprueba las rutas y tamaños. Luego sube cada archivo:

```powershell
rclone copyto (Join-Path $packagePath 'public.zip') "$remotePath/public.zip" --progress --s3-no-check-bucket --s3-upload-cutoff 64M --s3-chunk-size 64M
rclone copyto (Join-Path $packagePath 'mod.zip') "$remotePath/mod.zip" --progress --s3-no-check-bucket --s3-upload-cutoff 64M --s3-chunk-size 64M
```

Comprueba que cada comando termina correctamente antes de continuar. rclone usa
carga multipart para archivos grandes; cada parte cuenta como operación clase A.
Si se interrumpe, puedes repetir la carga, pero no des por garantizada la reanudación
exacta desde el último byte. Revisa también las cargas multipart incompletas y su
política de limpieza en R2.

Lista los objetos y sus tamaños:

```powershell
rclone ls "$remotePath"
```

Si quieres una verificación completa adicional, descarga a una carpeta nueva:

```powershell
$verifyPath = Join-Path $env:TEMP "0ad-r2-check-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $verifyPath
rclone copy "$remotePath" "$verifyPath" --progress
Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $packagePath 'public.zip'), (Join-Path $verifyPath 'public.zip')
Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $packagePath 'mod.zip'), (Join-Path $verifyPath 'mod.zip')
```

Los dos hashes de cada ZIP deben coincidir. Necesitas espacio libre equivalente a
los archivos descargados. Una coincidencia de tamaños por sí sola no verifica los bytes.

## 7. Activar una URL pública

### Prueba temporal sin dominio

En el bucket, entra en **Settings** y activa **Public Development URL** (`r2.dev`).
Copia la URL generada. Esta dirección tiene limitación de solicitudes y es para
desarrollo, no para el lanzamiento público.

### Publicación con dominio propio

1. Ten tu dominio como zona en la misma cuenta Cloudflare que R2. Para una
   configuración habitual, añade el dominio y completa el cambio de nameservers
   que indique Cloudflare.
2. En el bucket, abre **Settings → Custom Domains → Add**.
3. Introduce un subdominio dedicado, por ejemplo `assets.tudominio.com`.
4. Revisa el registro DNS propuesto y conecta el dominio.
5. Espera a que el estado y el certificado HTTPS estén activos.

La URL de un objeto será:

```text
https://assets.tudominio.com/releases/beta-001/public.zip
```

No agregues el nombre del bucket a esa URL. Abrir la raíz del dominio no lista sus
objetos, así que prueba una ruta completa. El acceso público permite descargar los
objetos a cualquiera que conozca sus URLs. CORS no convierte el bucket en privado.
Puedes desactivar `r2.dev` cuando uses el dominio propio.

Fuente: [buckets públicos y dominios](https://developers.cloudflare.com/r2/buckets/public-buckets/).

## 8. Configurar CORS para leer los bloques

En **Settings → CORS Policy**, agrega esta política desde la pestaña JSON del panel.
Reemplaza el origen por el de tu página de juego, incluyendo protocolo y puerto
cuando corresponda, sin rutas ni barra final:

```json
[
  {
    "AllowedOrigins": ["https://play.tudominio.com"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["Range"],
    "ExposeHeaders": ["Content-Range", "Accept-Ranges", "ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

Para pruebas locales puedes agregar `http://localhost:8080` a `AllowedOrigins`.
El permiso debe corresponder al origen que ejecuta el juego, aunque la landing esté
en otro dominio. `Content-Range` debe quedar expuesto: el código actual lee ese
encabezado y rechaza los bloques si no coincide exactamente con el manifiesto.

Si cambias CORS después de haber cacheado objetos en el dominio propio, purga la
caché afectada. Fuente: [configuración CORS de R2](https://developers.cloudflare.com/r2/buckets/cors/).

## 9. Probar HTTP antes de conectar el juego

En Windows usa `curl.exe` para evitar el alias de algunas versiones de PowerShell:

```powershell
$assetUrl = 'https://assets.tudominio.com/releases/beta-001/public.zip'
curl.exe -I "$assetUrl"
curl.exe -sS -D - -o NUL -H 'Origin: https://play.tudominio.com' -H 'Range: bytes=0-1023' "$assetUrl"
```

La segunda petición debe responder:

- Estado `206 Partial Content`.
- `Content-Range: bytes 0-1023/TOTAL`, con el tamaño real del ZIP.
- Un cuerpo de 1024 bytes.
- `Access-Control-Allow-Origin: https://play.tudominio.com`.
- `Access-Control-Expose-Headers` incluyendo `Content-Range`.

Repite la prueba con `mod.zip`. Conserva el tipo `application/zip` y no configures
`Content-Encoding: gzip` ni transformaciones sobre estos ZIP. Sus bytes deben
coincidir con los hashes del manifiesto.

Un dominio propio permite usar caché, pero hay límites de tamaño por objeto según
el plan de CDN. No supongas que un ZIP de 2 GB quedará cacheado; servirlo desde R2
y cachearlo en el borde son funciones diferentes.

## 10. Conectar el cargador del repositorio

**Esta guía no modifica el cargador ni publica una compilación.** El código actual
de `wasm/browser/application-archives.mjs` inicializa el servicio con
`baseURL: location.href`. `archive-blocks.mjs` resuelve `public.zip` y `mod.zip`
contra esa base. Por tanto, actualmente los busca junto a la página del juego.

Para descargar directamente de R2, la integración pendiente es pasar como base:

```text
https://assets.tudominio.com/releases/beta-001/
```

La barra final importa. Una implementación mantenible puede recibir esa base como
opción de `openArchiveService`, conservando `location.href` como valor local por
defecto. Hay que incorporar el cambio al paquete que se publique, revisar también
la ruta alternativa de descarga `installArchive` en `application.mjs` y verificar
los modos que se vayan a ofrecer. No asumas que un parámetro de URL para R2 ya existe.

Mantén `archive-blocks.json`, `application-data.json`, WASM y scripts del mismo
paquete que produjo esos ZIP. No reemplaces un ZIP publicado por otro diferente
bajo el mismo prefijo. Para actualizar, sube una versión nueva y después cambia
la configuración del despliegue.

Mantén HTML, módulos y workers en CasaOS al principio. Mover workers a otro origen
añade restricciones que no se resuelven solo con la política CORS de los ZIP.

No uses un proxy en CasaOS para descargar los ZIP desde R2 y reenviarlos a los
jugadores si tu objetivo es ahorrar subida doméstica: la descarga debe ir del
navegador a R2 directamente.

## 11. Verificar el juego completo

1. Sirve el juego mediante HTTPS y conserva la configuración de aislamiento de
   `wasm/deploy/nginx.conf`: COOP `same-origin` y COEP `require-corp`.
2. Abre DevTools en la página del juego y comprueba `crossOriginIsolated === true`.
3. Inicia el juego y revisa Network: los ZIP deben pedirse a R2 con respuestas 206.
4. Comprueba que no hay errores CORS, de aislamiento, de hashes ni de rangos.
5. Abre una partida y prueba el cierre. Repite una visita para comprobar IndexedDB.
6. Revisa las operaciones y el almacenamiento en el panel R2 tras las pruebas.

El smoke test existente, `wasm/deploy/smoke-test.py`, comprueba los archivos en
`/play/` del mismo origen. Habrá que adaptarlo si se separan las URLs de los ZIP;
su prueba actual no demuestra que la integración con R2 funcione.

Antes de publicar, revisa las licencias y fuentes correspondientes a la compilación
siguiendo `wasm/deploy/README.md`. Los cambios requieren revisión humana antes de
enviarlos al proyecto.

## 12. Problemas frecuentes

| Síntoma | Qué revisar |
| --- | --- |
| 401/403 al subir | Credenciales, endpoint, alcance del token y `--s3-no-check-bucket`. |
| 403 al abrir el objeto | Acceso público activado en la URL elegida. |
| 404 | Prefijo, versión, nombre y mayúsculas/minúsculas de la clave. |
| CORS en navegador, pero curl funciona | Origen exacto permitido y encabezado `Origin` en la prueba. |
| Error de `Content-Range` | Estado 206, encabezado expuesto y tamaño igual al manifiesto. |
| Error de integridad | ZIP y manifiesto de versiones distintas, o transformación de bytes. |
| Falta `SharedArrayBuffer` | HTTPS y aislamiento en el servidor que entrega el juego. |
| Los ZIP siguen saliendo de casa | El cargador todavía usa su base local o hay un proxy intermedio. |

## Referencias

- [Subir objetos](https://developers.cloudflare.com/r2/objects/upload-objects/).
- [rclone con R2](https://developers.cloudflare.com/r2/examples/rclone/).
- [Acceso público y dominios](https://developers.cloudflare.com/r2/buckets/public-buckets/).
- [CORS](https://developers.cloudflare.com/r2/buckets/cors/).
- [Precios](https://developers.cloudflare.com/r2/pricing/).
- [Despliegue web de este repositorio](wasm/deploy/README.md).

Los pasos se contrastaron con la documentación, pero no se ejecutaron contra una
cuenta R2 ni se verificó una publicación real como parte de la creación de esta guía.
