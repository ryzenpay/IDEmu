# syntax=docker/dockerfile:1
# IDEmu em container: compila os QEMU com os dispositivos do projeto (src/qemu) e o glhost,
# e empacota o servidor web (GUI em http://127.0.0.1:8765). TCG puro — não precisa de /dev/kvm.
# Uso normal via docker-compose (docker-compose.yml + docs/DOCKER.md).

# ---------------------------------------------------------------- binaries
FROM debian:bookworm-slim AS binaries
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential pkg-config ninja-build meson python3 python3-venv perl curl patch ca-certificates \
        libglib2.0-dev libpixman-1-dev libfdt-dev flex bison \
        freeglut3-dev libgl1-mesa-dev libglew-dev libx11-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY tools ./tools
COPY src/shim ./src/shim
COPY src/qemu ./src/qemu
COPY src/glhost ./src/glhost
# QEMU 11.1.2 oficial + omap5-uevm (iDrive 5/6), idemu-shm (iDrive 7), virt+shm (iDrive 8)
ARG QEMU_VERSION=11.1.2
RUN curl -fL "https://download.qemu.org/qemu-${QEMU_VERSION}.tar.xz" -o /qemu.tar.xz \
    && QEMU_BUILD_DIR=/qemuwork bash tools/qemu/build.sh /qemu.tar.xz \
    && bash src/glhost/build.sh \
    && ls -l /build/bin

# ---------------------------------------------------------------- runtime
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libpixman-1-0 libfdt1 zlib1g \
        libgl1 libegl1 libgles2 libglew2.2 libglut3.12 libx11-6 libgl1-mesa-dri \
        xvfb xkb-data \
        openssh-server openssh-client qemu-utils \
        procps curl ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /run/sshd
WORKDIR /app
COPY . .
COPY --from=binaries /build/bin /app/bin
RUN chmod +x docker/entrypoint.sh

ENV LIBGL_ALWAYS_SOFTWARE=1 \
    IDEMU_SMP=2 \
    PYTHONUNBUFFERED=1
EXPOSE 8765
VOLUME ["/app/environments", "/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD curl -fsS http://127.0.0.1:8765/ >/dev/null || exit 1
ENTRYPOINT ["/app/docker/entrypoint.sh"]
