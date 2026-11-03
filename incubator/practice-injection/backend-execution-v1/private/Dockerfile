FROM python:3.12.11-slim@sha256:47ae396f09c1303b8653019811a8498470603d7ffefc29cb07c88f1f8cb3d19f
RUN pip install --no-cache-dir 'psycopg[binary]==3.2.10' 'typing-extensions==4.16.0'
WORKDIR /work
USER 65534:65534
ENTRYPOINT ["python", "-u", "server.py"]
