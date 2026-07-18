FROM python:3.12-alpine

WORKDIR /app
# 01777 keeps the shared marker writable when a container platform overrides
# USER with an arbitrary non-root uid, while the sticky bit protects temp files.
RUN mkdir -p /koth && chmod 01777 /koth
COPY --chown=nobody:nogroup app.py /app/app.py

USER nobody
EXPOSE 8080
CMD ["python", "-u", "/app/app.py"]
