FROM python:3.12-alpine@sha256:c5ba3deef00c7758561a0f03c26f44f10589263d40e732b8748e0d1f38f6dd89
WORKDIR /app
COPY --chown=nobody:nogroup server.py exercise.py ./
RUN printf ok > /app/health-ok && touch /flag && chown nobody:nogroup /flag
USER nobody
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=2s --retries=3 CMD wget -Y off -T 2 -qO - http://127.0.0.1:8080/health | cmp -s /app/health-ok
CMD ["python", "-B", "/app/server.py"]
