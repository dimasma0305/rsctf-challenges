# Pin or mirror this base when the build host must avoid Docker Hub.
FROM python:3.12-alpine AS tests

WORKDIR /test
COPY app.py reporter.py test_reporting.py /test/
RUN python -m unittest -v test_reporting.py

FROM python:3.12-alpine AS runtime

WORKDIR /app
COPY --from=tests --chown=nobody:nogroup /test/app.py /app/app.py
COPY --from=tests --chown=nobody:nogroup /test/reporter.py /app/reporter.py

USER nobody
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=2s --retries=3 \
  CMD ["python", "-c", "import sys,urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=2).read().strip()!=b'ok')"]
CMD ["python", "-u", "/app/app.py"]
