# Repositorio unificado de 0 A.D. WebAssembly

## Una raíz para las fuentes y el port

`0adwebassembly` contiene ahora las fuentes del motor y la capa para navegador.
El trabajo diario se realiza en esta carpeta:

```text
0adwebassembly/
├── source/            # Motor original y adaptaciones del port
├── binaries/data/     # Scripts y configuración; datos binarios locales ignorados
├── build/             # Soporte de compilación original
├── libraries/         # Soporte de dependencias del motor
├── wasm/              # Navegador, arnés, herramientas y empaquetado
├── docs/wasm/         # Informes y evidencias seleccionadas
├── plan/              # Criterios y trabajo pendiente
├── patches/           # Registro histórico de la antigua capa
└── tools/assemble.py  # Comprobador de compatibilidad de la estructura
```

`build/` contiene archivos fuente del sistema de compilación: no debe confundirse
con sus salidas generadas. `wasm/build/`, `wasm/dist/` y las demás salidas se
mantienen ignoradas. Del mismo modo, el soporte de bibliotecas puede estar
versionado sin incluir sus binarios o las dependencias descargadas.

El pin del juego se conserva en [`BASE_COMMIT.txt`](../../BASE_COMMIT.txt).
Cambiar la disposición local no equivale a actualizar ese pin.

## Qué cambia respecto al flujo anterior

Antes, este repositorio guardaba una capa y `tools/assemble.py build` creaba un
worktree en `../0ad-wasm` a partir de un clon oficial en `../0ad`. Después de editar
el árbol completo, `export` regeneraba parches y copiaba archivos de vuelta.

Ahora las modificaciones se hacen directamente aquí. No se necesita clonar otro
árbol para disponer de las fuentes, crear un worktree ni sincronizar las carpetas
tras cada cambio.

- `python tools/assemble.py check` comprueba la estructura unificada.
- `python tools/assemble.py build` conserva el nombre antiguo como comprobación;
  no aplica parches ni crea otro árbol.
- `python tools/assemble.py export` explica que los archivos se editan y versionan
  directamente. No regenera `patches/`.

Los parches existentes se conservan como referencia de la migración. **No deben
aplicarse al código de esta raíz:** sus modificaciones ya están incorporadas.
La fuente de verdad para futuros cambios es el archivo correspondiente del motor
o de la capa web.

El clon oficial `0ad` se conserva intacto. Los archivos locales del antiguo
worktree se trasladaron a esta raíz; las variantes diferentes quedan respaldadas
en `.git/local-integration-backups/`. La ruta `0ad-wasm` ahora es un enlace de
compatibilidad a esta carpeta, sin otro repositorio ni copia del motor.

## Recursos grandes fuera del versionado

El código y los datos del juego tienen necesidades distintas. Se incluyen las
fuentes, los scripts, la configuración y la documentación; los recursos binarios
pesados siguen fuera del versionado: texturas, modelos, audio, tipografías y mapas
binarios, además de los archivos compilados y paquetes de distribución.

Si esos archivos ya están presentes localmente, pueden seguir utilizándose sin
incorporarlos al índice de Git. Las reglas de exclusión no borran sus copias del
disco. Los manifiestos, resúmenes de resultados, hashes y evidencias representativas
siguen siendo útiles y se conservan según su política de versionado.

Un clon nuevo necesita obtener por separado los datos originales compatibles con
el pin antes de las tareas que los consuman. Para la ejecución web, los archivos
`public.zip` y `mod.zip` del paquete correspondiente se sirven desde el despliegue
configurado; no forman parte de las fuentes publicadas. La
[guía de R2](../../GUIA-CLOUDFLARE-R2.md) describe su alojamiento.

No se deben confundir los ZIP de datos con la imagen Docker ni con el motor WASM.
Cada paquete debe conservar la correspondencia entre su motor, manifiestos,
scripts y recursos; la reorganización no autoriza mezclarlos entre versiones.

## Compilar y comprobar

Los scripts de `wasm/scripts/` calculan sus rutas desde esta raíz. Elige el objetivo
y las dependencias descritas en los informes de la fase correspondiente; no ejecutes
los comandos desde una copia separada del proyecto.

Comprobaciones de herramientas que no implican una compilación completa:

```powershell
python tools/assemble.py check
python -m unittest discover -s wasm/scripts -p "test*.py"
node --test wasm/scripts/test-webgpu-command-ring.mjs wasm/scripts/test-webgpu-pipeline-cache.mjs
```

Algunas pruebas diferenciales necesitan archivos o casos generados del motor.
Las pruebas de navegador requieren un paquete construido y un servidor con las
cabeceras adecuadas. La presencia de todas las fuentes no sustituye esas
precondiciones.

Reunir las carpetas no recompila el motor, no repite las mediciones previas y no
cierra los gates de rendimiento o paridad. El lanzador actual selecciona el
intérprete C++ de SpiderMonkey; los límites de comparación con medidas antiguas
están documentados en la
[continuación del 2 de noviembre](phase-4-5-continuation-2026-11-02.md).

## Licencias y revisión

Los archivos originales mantienen sus autores, avisos y licencias. La estructura
unificada no cambia las condiciones de código, arte o dependencias. Consulta
[`LICENSE.md`](../../LICENSE.md) y los avisos específicos antes de redistribuir
fuentes, ejecutables o datos del juego.

## Limpieza de los arboles anteriores

El antiguo worktree `0ad-wasm` se retira tras trasladar sus archivos locales a esta raiz. La ruta antigua queda como enlace de compatibilidad a `0adwebassembly`, sin una segunda copia del motor. Los archivos diferentes y la configuracion anterior se respaldan en `.git/local-integration-backups/`. El clon oficial `0ad` se conserva intacto.
