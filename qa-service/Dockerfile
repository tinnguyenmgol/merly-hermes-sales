FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/home/qa TMPDIR=/run/qa MERLY_QA_STATE_DIR=/data
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && mkdir -p /data /run/qa /home/qa && chown -R 10001:10001 /data /run/qa /home/qa
COPY qa_transport.py qa_core.py qa_server.py ./
USER 10001:10001
EXPOSE 8080
CMD ["python","qa_server.py"]
