# 0 A.D. WebAssembly

Capa que lleva [0 A.D.](https://play0ad.com) al navegador: el motor original (Pyrogenesis)
compilado con Emscripten, con renderizado WebGPU/WebGL 2. Este repositorio contiene **solo la
capa de conversión**; el juego se toma del repositorio oficial de 0 A.D., en el commit fijado en
`BASE_COMMIT.txt`.

## Qué hay aquí

| Ruta | Contenido |
| --- | --- |
| `wasm/` | Código del navegador, arnés C++, Dockerfiles, scripts de compilación y despliegue |
| `source/` | Archivos nuevos que la capa agrega al motor (backend WebGPU, ayudantes de simulación e IA) |
| `patches/` | Cambios a archivos existentes de 0 A.D., un parche por área |
| `docs/wasm/` | Documentación y evidencias de cada fase |
| `plan/` | Planes de cada fase |
| `BASE_COMMIT.txt` | Commit oficial de 0 A.D. sobre el que se aplica la capa |
| `GUIA-CLOUDFLARE-R2.md` | Guía para alojar los archivos del juego en Cloudflare R2 |
| `tools/assemble.py` | Arma el árbol completo y vuelca sus cambios a este repositorio |

## Armar el árbol completo

Requisitos: git, git-lfs y Python 3.

```text
git clone https://gitea.wildfiregames.com/0ad/0ad.git ../0ad
python tools/assemble.py build
```

`build` crea `../0ad-wasm`: un worktree del clon oficial en `BASE_COMMIT`, con `patches/`
aplicados y los archivos de esta capa copiados encima. Es el mismo árbol que tenía el fork
completo, así que las instrucciones de compilación de `docs/wasm/` se ejecutan ahí. Otras rutas:
`--official` y `--dest`.

## Trabajar sobre el árbol completo

En `../0ad-wasm`, `git status` muestra exactamente la capa: los archivos modificados son
cambios al motor y los no rastreados son archivos propios. Después de trabajar ahí:

```text
python tools/assemble.py export
```

`export` regenera `patches/` y copia aquí los archivos propios nuevos o modificados; luego se
revisan y se hace commit en este repositorio. Para rehacer el árbol desde cero:
`git -C ../0ad worktree remove --force ../0ad-wasm` y otra vez `build`.

Para mover la capa a un commit más nuevo de 0 A.D., cambia `BASE_COMMIT.txt` y vuelve a armar;
si un parche ya no encaja, `git apply` indica cuál y hay que rehacerlo en el árbol completo.

## Acerca de este proyecto

Este repositorio es un fork de **0 A.D.**, el juego de estrategia en tiempo real libre y de
código abierto de [Wildfire Games](https://play0ad.com). Está pensado para experimentar,
desarrollar y mejorar el juego con la comunidad, y se basa en el código fuente creado y
mantenido por sus autores y colaboradores.

### Licencia y atribución

**Todos los derechos, derechos de autor y términos de licencia originales pertenecen al
proyecto 0 A.D. y a sus autores y colaboradores.** Este repositorio no reclama la propiedad
del código fuente, los recursos ni la propiedad intelectual del proyecto original.

La licencia del proyecto original sigue aplicándose a todo el código y los recursos heredados
(ver `LICENSE.md`); las modificaciones y contribuciones de este fork quedan sujetas a la
licencia aplicable. Este fork es un esfuerzo de desarrollo independiente, no afiliado ni
respaldado por los desarrolladores de 0 A.D.

**Todo el crédito es para el equipo de 0 A.D. y sus colaboradores.**
