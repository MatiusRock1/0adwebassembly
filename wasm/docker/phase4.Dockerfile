FROM 0ad-wasm-phase3:o3-lto-cached AS dependencies
COPY scripts/phase4-dependencies.sh /opt/phase4-dependencies.sh
RUN bash /opt/phase4-dependencies.sh
