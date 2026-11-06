FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir flask==3.0.3 gunicorn==22.0.0
COPY . /app
ENV PORTAL_DB=/data/portal.db EVIDENCE_DIR=/evidence
EXPOSE 8080
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:8080", "app:app"]
