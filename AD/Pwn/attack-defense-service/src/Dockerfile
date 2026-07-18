FROM python:3.12-alpine

WORKDIR /app
COPY --chown=nobody:nogroup app.py /app/app.py

USER nobody
EXPOSE 8080
CMD ["python", "-u", "/app/app.py"]
