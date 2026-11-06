FROM python:3.12-slim
RUN pip install --no-cache-dir pyyaml==6.0.2 \
 && apt-get update && apt-get install -y --no-install-recommends curl jq less nano && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/audit
COPY collect.py analyze.py /opt/audit/
RUN printf '#!/bin/sh\nexec python3 /opt/audit/collect.py "$@"\n' > /usr/local/bin/collect \
 && printf '#!/bin/sh\nexec python3 /opt/audit/analyze.py "$@"\n' > /usr/local/bin/analyze \
 && printf '#!/bin/sh\ncollect && analyze\n' > /usr/local/bin/audit \
 && chmod +x /usr/local/bin/collect /usr/local/bin/analyze /usr/local/bin/audit
ENV EVIDENCE_DIR=/evidence
