ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:3.21
FROM ${BUILD_FROM}
RUN apk add --no-cache python3 traceroute
COPY run.sh /run.sh
COPY app.py /app.py
COPY mikrotik.py /mikrotik.py
RUN chmod +x /run.sh
CMD ["/run.sh"]
