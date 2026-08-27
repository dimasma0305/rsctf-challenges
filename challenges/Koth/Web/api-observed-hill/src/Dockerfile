# Replace this with a pinned internal base when the build host must avoid
# Docker Hub.
FROM python:3.12-alpine

WORKDIR /app
COPY --chown=nobody:nogroup app.py /app/app.py

USER nobody
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=2s --retries=3 \
  CMD ["python", "-c", "import sys,urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=2).read().strip()!=b'ok')"]
CMD ["python", "-u", "/app/app.py"]
