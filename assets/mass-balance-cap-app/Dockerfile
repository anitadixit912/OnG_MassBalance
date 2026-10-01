# ── Stage 1: Build Node.js CAP app ─────────────────────────────────────────
FROM node:22-alpine AS cap-build

WORKDIR /cap

RUN apk add --no-cache python3 make g++
RUN npm install -g @sap/cds-dk@^10

COPY package.json ./
RUN npm install

COPY . .
# Override cdsrc to always use SQLite in Docker (ignore NODE_ENV=production HANA config)
RUN echo '{"requires":{"db":{"kind":"sqlite","credentials":{"url":"mass-balance.db"}},"auth":{"kind":"dummy"}},"features":{"fiori_preview":true}}' > .cdsrc.docker.json
RUN cds deploy --to sqlite:mass-balance.db

# ── Stage 2: Final image — Python + Node.js + supervisord ──────────────────
FROM python:3.11-slim

# Install Node.js 22 and supervisord
RUN apt-get update && apt-get install -y curl supervisor && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for orchestrator
COPY orchestrator-requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/orchestrator-requirements.txt

# Copy orchestrator source
COPY orchestrator/ /app/orchestrator/

# Copy built CAP app from stage 1
COPY --from=cap-build /cap /cap

# Install cds-serve globally in final image
RUN npm install -g @sap/cds-dk@^10

# Supervisord config + CAP startup script
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY start-cap.sh /cap/start-cap.sh
RUN chmod +x /cap/start-cap.sh

EXPOSE 4004 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
