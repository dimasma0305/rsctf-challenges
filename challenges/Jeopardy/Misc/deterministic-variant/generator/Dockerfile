FROM python:3.12-alpine@sha256:d09d15e60962ca365d1cd544a48773bac9d33f2fb1b00f2aa0deec78ade7dc31

LABEL org.opencontainers.image.source="https://github.com/dimasma0305/rsctf-challenges" \
      org.opencontainers.image.description="Deterministic rsctf challenge-variant generator example" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    PYTHONUNBUFFERED=1

WORKDIR /generator
COPY --chmod=0555 generate.py /generator/generate.py

USER 65532:65532
ENTRYPOINT ["python3", "-I", "/generator/generate.py"]
