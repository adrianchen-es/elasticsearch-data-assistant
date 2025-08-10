FROM node:20-alpine
WORKDIR /srv

RUN npm cache clean --force && \
    rm -rf /root/.npm /root/.node-gyp /root/.config

COPY package*.json ./
RUN npm install --omit=dev
COPY src ./src

ENV NODE_ENV=production \
    PORT=3100 \
    OTEL_SERVICE_NAME=es-data-assistant-gateway \
    OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318/v1/traces
EXPOSE 3100
CMD ["node", "src/server.js"]