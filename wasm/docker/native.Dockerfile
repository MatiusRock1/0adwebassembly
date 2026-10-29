FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55 AS native-toolchain
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git git-lfs build-essential cmake ninja-build python3 \
    python3-venv python3-pip pkg-config curl unzip zip xz-utils patch \
    autoconf automake libtool m4 subversion clang llvm \
    libboost-dev libboost-system-dev libboost-filesystem-dev libcurl4-gnutls-dev \
    libenet-dev libfmt-dev libfreetype-dev libicu-dev libogg-dev libopenal-dev \
    libpng-dev libsdl2-dev libsodium-dev libvorbis-dev libxml2-dev \
    libgl1-mesa-dev zlib1g-dev time \
    && rm -rf /var/lib/apt/lists/*
ENV RUSTUP_HOME=/opt/rustup CARGO_HOME=/opt/cargo
ENV PATH="/opt/cargo/bin:${PATH}"
RUN curl -fLo /tmp/rustup-init https://static.rust-lang.org/rustup/archive/1.28.2/x86_64-unknown-linux-gnu/rustup-init \
    && curl -fLo /tmp/rustup-init.sha256 https://static.rust-lang.org/rustup/archive/1.28.2/x86_64-unknown-linux-gnu/rustup-init.sha256 \
    && cd /tmp && sha256sum -c rustup-init.sha256 \
    && chmod +x rustup-init \
    && ./rustup-init -y --no-modify-path --profile minimal --default-toolchain 1.85.1 \
    && cargo install --locked cbindgen --version 0.29.0 \
    && rm -f /tmp/rustup-init /tmp/rustup-init.sha256
WORKDIR /build/0ad

FROM native-toolchain AS native-checkout
# 0 A.D. oficial: es el que tiene BASE_COMMIT y su historial completo.
ARG SOURCE_URL=https://gitea.wildfiregames.com/0ad/0ad.git
ARG BASE_COMMIT=40b8794eecb9618da69e10bacffa8814c561aa51
RUN GIT_LFS_SKIP_SMUDGE=1 git clone --no-checkout "$SOURCE_URL" /build/0ad \
    && git lfs install --local \
    && GIT_LFS_SKIP_SMUDGE=1 git checkout --detach "$BASE_COMMIT" \
    && test "$(git rev-parse HEAD)" = "$BASE_COMMIT" \
    && mkdir -p /evidence \
    && printf '%s\n' "$BASE_COMMIT" > /evidence/BASE_COMMIT.txt

FROM native-checkout AS native-assets
# Los objetos descargados quedan en cache BuildKit; el checkout hidratado
# queda en la capa de imagen. Un build fallido puede reutilizar la cache.
RUN --mount=type=cache,id=0ad-phase1-lfs,target=/cache/lfs,sharing=locked \
    git config lfs.storage /cache/lfs \
    && git config lfs.url https://gitea.wildfiregames.com/0ad/0ad.git/info/lfs \
    && GIT_TERMINAL_PROMPT=0 git lfs fetch origin "$(cat /evidence/BASE_COMMIT.txt)" \
    && git lfs checkout \
    && git lfs fsck \
    && git lfs ls-files --json > /evidence/lfs-inventory-complete.json \
    && git config --unset lfs.storage \
    && printf 'LFS checkout and fsck OK\n' > /evidence/lfs-success.txt

FROM native-assets AS native-dependencies
COPY scripts/image-native.sh /opt/wasm/image-native.sh
ARG NATIVE_JOBS=4
RUN bash /opt/wasm/image-native.sh dependencies "$NATIVE_JOBS"

FROM native-dependencies AS native-nvtt
ARG NATIVE_JOBS=4
# La suite nativa incluye TextureConverter: requiere NVTT aunque la futura
# simulacion WASM headless pueda excluirlo. Mantener las demas deps cacheadas.
RUN JOBS="-j$NATIVE_JOBS" bash libraries/source/nvtt/build.sh \
    && cp libraries/source/nvtt/bin/* binaries/system/ \
    && sha256sum libraries/source/nvtt/nvtt-28209.tar.xz > /evidence/native-nvtt-source.sha256

FROM native-nvtt AS native-engine
COPY scripts/image-baseline.sh /opt/wasm/image-baseline.sh
ARG NATIVE_JOBS=4
RUN bash /opt/wasm/image-baseline.sh build "$NATIVE_JOBS"

FROM native-engine AS native-baseline
RUN bash /opt/wasm/image-baseline.sh tests

# Exportacion opcional de logs sin iniciar un contenedor.
FROM scratch AS native-evidence
COPY --from=native-baseline /evidence/ /

# Etapa predeterminada: imagen con motor y tests ya compilados/verificados.
FROM native-baseline AS native-final
LABEL org.opencontainers.image.description="0 A.D. Linux baseline built and tested during docker build"
WORKDIR /build/0ad/binaries/system
CMD ["bash"]
