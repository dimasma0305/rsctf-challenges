FROM rsctf-starter
WORKDIR /app
COPY --chown=10000:10000 app.py banner.txt ./
RUN touch /flag && chown 10000:10000 /app /flag
ENV RSCTF_FLAG_FILE=/flag PYTHONDONTWRITEBYTECODE=1
USER 10000:10000
EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=3s --start-period=2s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).read() != b'ok')"]
CMD ["python", "-u", "/app/app.py"]
