# Serves an already built browser package: build it with the phase 4.5
# pipeline, then assemble this image's context with prepare-context.py.
#   python wasm/deploy/prepare-context.py --package wasm/dist/<package> --output wasm/build/deploy-context
#   docker build -t 0ad-wasm-web wasm/build/deploy-context
#   docker run --rm -p 8080:8080 0ad-wasm-web
FROM nginx:1.27-alpine

COPY --chmod=755 15-archive-urls.sh /docker-entrypoint.d/15-archive-urls.sh

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY site/ /usr/share/nginx/html/
COPY play/ /usr/share/nginx/html/play/
COPY licenses/ /usr/share/nginx/html/licenses/

EXPOSE 8080
