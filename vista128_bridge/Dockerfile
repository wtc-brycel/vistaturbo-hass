# Home Assistant base 3.24; immutable multi-architecture manifest digest.
FROM ghcr.io/home-assistant/base:3.24@sha256:93ef607824e3f27e868f11b10938283a98bf880ed57bcf8eaa81c6c2d521f6f5

ARG BUILD_VERSION
ARG BUILD_ARCH

RUN apk add --no-cache python3 py3-pip

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

COPY run.sh /run.sh
COPY app /app

RUN chmod a+x /run.sh

LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

CMD ["/run.sh"]
