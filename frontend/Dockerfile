###############################################################################
# Frontend (Nginx) — build multi-stage
#   Etapa 1 "builder": valida y pre-comprime los assets estáticos (gzip), para
#                      que Nginx sirva payloads más pequeños con menos CPU en runtime.
#   Etapa 2 "runtime": base nginx-unprivileged — corre como no-root (uid 101) y
#                      escucha en 8080 por defecto. Solo los assets finales +
#                      la config llegan a la imagen.
###############################################################################

# ---- Etapa 1: builder -------------------------------------------------------
FROM alpine:3.21 AS builder

WORKDIR /build
RUN apk add --no-cache gzip
COPY html/ ./html/

# Pre-comprime los assets de texto (conservados junto a los originales con -k) para gzip_static.
RUN find ./html -type f \( -name '*.html' -o -name '*.css' -o -name '*.js' \) \
    -exec gzip -9 -k {} \;

# ---- Etapa 2: runtime -------------------------------------------------------
# nginx-unprivileged corre como no-root (uid 101) y escucha en 8080 — un gran
# ajuste para SecurityContexts de Pod restrictivos.
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# Reemplaza la config del sitio por defecto con la nuestra (proxy inverso al backend).
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Incluye los assets estáticos (pre-comprimidos).
COPY --from=builder /build/html /usr/share/nginx/html

EXPOSE 8080
# USER ya es 101 (no-root) en la imagen base; se declara aquí por claridad.
USER 101
