# =====================================================================
# Multi-stage Dockerfile
#
# Stage 1 "builder": full Go toolchain (compiler, stdlib sources, module
# cache) compiles a static binary. This stage is large but is DISCARDED
# from the final image - it never ships.
#
# Stage 2 (final): scratch (an explicitly empty base image - literally
# zero bytes of OS). Only the compiled binary is copied in with
# `COPY --from=builder`. Nothing else from the builder - no compiler,
# no shell, no package manager - makes it into the image that actually
# runs in production.
# =====================================================================

# ---- Stage 1: builder ----
FROM golang:1.23-alpine AS builder
WORKDIR /src

# Copy module file first so `go build` dependency resolution is cached
# independently of source-code changes (layer caching).
COPY app/go.mod .
COPY app/main.go .

# CGO disabled + static flags -> a fully static, standalone binary that
# has no runtime dependency on glibc/musl, so it can run on `scratch`.
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -o /out/app main.go

# ---- Stage 2: runtime ----
FROM scratch AS final

# Run as a non-root numeric UID. `scratch` has no /etc/passwd, so a
# named user is not possible, but a numeric UID still works.
USER 65534

COPY --from=builder /out/app /app

EXPOSE 8080

ENTRYPOINT ["/app"]
