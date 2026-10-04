FROM mcr.microsoft.com/devcontainers/python:dev-3.14-bookworm

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL --retry 3 --retry-delay 2 https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key -o /tmp/nodesource.gpg.key && \
    gpg --batch --yes --dearmor -o /etc/apt/keyrings/nodesource.gpg /tmp/nodesource.gpg.key && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_24.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/* /tmp/nodesource.gpg.key && \
    npm install -g npm@latest && \
    npm install -g @anthropic-ai/claude-code