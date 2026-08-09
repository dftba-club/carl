FROM python:3.13-slim
WORKDIR /app

# Release version, injected by the publish workflow's build-arg; 'dev' for local builds.
ARG VERSION=dev
ENV VERSION=$VERSION

# Env var which will be the lower-level user
ENV USER=bot
ENV GROUP_NAME=group
ENV OWNER=user@example.com
ENV SERVER_URL=https://localhost
ENV BOT_NAME=carl
ENV ACCESS_TOKEN=SECRET_KEY
ENV YT_URL=https://www.youtube.com/feeds/videos.xml?channel_id=0000
ENV POD_URL=https://localhost
ENV DELAY=10

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Do all of this work as ROOT
USER root

# Create User
RUN adduser ${USER} --system --no-create-home

# Install pinned dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy in the startup script & bot script
COPY bot.py .

# The main loop touches this file every ~20s (see touch_heartbeat in bot.py); a stale
# heartbeat means the process is hung, not just between polls -- socket.setdefaulttimeout
# bounds individual network calls but not a wedged process. On plain (non-swarm) compose
# this surfaces health status for monitoring/watchtower; it does not restart the container.
HEALTHCHECK --interval=60s --timeout=5s --start-period=60s --retries=3 \
  CMD ["python", "-c", "import time,sys; d=time.time()-float(open('/tmp/carl-heartbeat').read()); sys.exit(0 if d<120 else 1)"]

# Set user during the container runtime
USER ${USER}
# Let's go!
CMD [ "python", "/app/bot.py" ]
