# Testing image: amd64 only. Browser dependencies are preinstalled.
FROM mcr.microsoft.com/playwright/python:v1.56.0-noble
ARG BUILD_VERSION=0.1.0-alpha
ARG BUILD_ARCH=amd64
LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}"
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Prague
WORKDIR /app
RUN python -m pip install --no-cache-dir playwright==1.56.0 paho-mqtt==2.1.0
COPY app.py /app/app.py
CMD ["python", "/app/app.py"]
