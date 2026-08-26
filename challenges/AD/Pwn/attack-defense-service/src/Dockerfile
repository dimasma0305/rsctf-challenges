# Replace this with a pinned internal base when the build host must avoid
# Docker Hub.
FROM python:3.12-alpine

WORKDIR /app
COPY --chown=nobody:nogroup app.py /app/app.py

# rsctf refreshes this file every round with `docker exec`. Keep it outside the
# image layer and writable by the non-root runtime user.
RUN mkdir -p /run/rsctf && chown nobody:nogroup /run/rsctf
ENV RSCTF_FLAG_FILE=/run/rsctf/flag

USER nobody
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=2s --retries=3 \
  CMD ["python", "-c", "import socket,sys; s=socket.create_connection(('127.0.0.1',8080),2); s.sendall(b'PING\\n'); sys.exit(s.makefile('rb').readline(4097)!=b'PONG\\n')"]
CMD ["python", "-u", "/app/app.py"]
