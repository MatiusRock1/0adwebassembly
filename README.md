# 0 A.D. WebAssembly

Port experimental de [0 A.D.](https://play0ad.com/) al navegador: el motor original
Pyrogenesis compilado con Emscripten, con renderizado WebGPU/WebGL 2.

**Las fuentes del motor y la capa web se trabajan juntas en este repositorio.**
`source/`, los scripts originales del juego y `wasm/` comparten la misma raíz.
No hace falta mantener otro árbol `0ad-wasm` ni exportar parches después de editar.

El punto de partida oficial está fijado en [`BASE_COMMIT.txt`](BASE_COMMIT.txt).
La integración del port y sus resultados se documentan en [`docs/wasm/`](docs/wasm/).

## Qué hay aquí

| Ruta | Contenido |
| --- | --- |
| `source/` | Código del motor y adaptaciones del port, incluido el backend WebGPU |
| `binaries/data/` | Scripts, configuración y otros archivos del juego; los recursos binarios pesados se mantienen fuera de Git |
| `build/`, `libraries/` | Instrucciones y soporte originales de compilación; las salidas y dependencias generadas se ignoran |
| `wasm/` | Lanzador del navegador, arnés C++, Dockerfiles, pruebas y herramientas de empaquetado |
| `docs/wasm/` | Documentación, resultados y evidencias seleccionadas |
| `plan/` | Planes de trabajo y criterios de aceptación |
| `patches/` | Referencia histórica de la antigua capa separada; no se aplica al árbol actual |
| `tools/assemble.py` | Verificación de compatibilidad de la estructura unificada |
| `GUIA-CLOUDFLARE-R2.md` | Guía para alojar los archivos del juego en Cloudflare R2 |

## Trabajar en el proyecto

Abre esta carpeta como raíz del proyecto y edita directamente las fuentes en
`source/`, los scripts del juego o los archivos de `wasm/`. Los cambios se revisan
y versionan aquí, sin un paso posterior de `export`.

Para comprobar que está disponible la estructura del motor:

```powershell
python tools/assemble.py check
```

Por compatibilidad, `python tools/assemble.py build` comprueba también la estructura:
no crea un worktree ni aplica los parches antiguos. `export` explica el nuevo flujo.

Las instrucciones de compilación y empaquetado siguen en los scripts de
`wasm/scripts/` y en los [resultados de fase 4.5](docs/wasm/phase-4-5-results.md).
Se ejecutan desde esta raíz. Dependiendo del objetivo necesitan Docker,
Emscripten, las bibliotecas y los datos originales indicados por cada fase.

[Organización del repositorio unificado](docs/wasm/unified-repository.md)
detalla las carpetas, los recursos externos y la migración del flujo anterior.

## Datos, compilaciones y distribución

Reunir el código no significa incorporar los archivos grandes a Git. Texturas,
modelos, audio, fuentes y mapas binarios originales se mantienen como datos locales
o de distribución y están excluidos del versionado según `.gitignore`.
Los paquetes `public.zip` y `mod.zip`, los motores compilados y las carpetas de
salida tampoco se suben al repositorio.

Un clon de las fuentes no sustituye esos datos. Para ejecutar o empaquetar el juego
hay que disponer de los recursos originales compatibles con el pin y del runtime
adecuado. Conserva la procedencia y las licencias al obtenerlos o distribuirlos.

## Verificación

Desde esta raíz se pueden ejecutar las pruebas de herramientas y algunas
regresiones de la capa web:

```powershell
python -m unittest discover -s wasm/scripts -p "test*.py"
node --test wasm/scripts/test-webgpu-command-ring.mjs wasm/scripts/test-webgpu-pipeline-cache.mjs
```

Estos comandos no recompilan el motor ni acreditan por sí solos rendimiento,
compatibilidad de navegadores o aceptación de una partida completa.

## Licencia y atribución

0 A.D. es software libre desarrollado por **Wildfire Games y sus colaboradores**.
Este proyecto conserva sus fuentes y atribuciones; no reclama la propiedad del
juego, sus recursos ni la propiedad intelectual de sus autores.

El código original y sus modificaciones quedan sujetos a las licencias aplicables;
consulta [`LICENSE.md`](LICENSE.md) y los avisos de cada archivo. El código del
motor se distribuye bajo GPL-2.0-or-later y el arte y audio originales bajo
CC BY-SA 3.0, con las condiciones específicas de sus recursos.

El port es un trabajo independiente, no afiliado ni respaldado por Wildfire Games.
La reorganización del repositorio no cambia esas licencias ni cierra los criterios
de aceptación que siguen pendientes en los planes y resultados.
