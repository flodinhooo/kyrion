FROM python:3.12-slim-trixie
RUN apt-get update && apt-get install -y --no-install-recommends gnupg openssl curl ca-certificates binutils \
    && rm -rf /var/lib/apt/lists/*
LABEL io.kyrion.test-fixture="true"
RUN pip install --no-cache-dir PyInstaller==6.22.3 cryptography==50.0.2
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /installer
ENTRYPOINT ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
