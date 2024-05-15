# set alpine as the base image of the Dockerfile
FROM python:3.9-slim
WORKDIR /app
# Env var which will be the lower-level user
ENV USER bot
ENV GROUP_NAME group
ENV OWNER user@example.com
ENV SERVER_URL https://localhost
ENV BOT_NAME carl
ENV CLIENT_KEY SECRET_KEY
ENV CLIENT_SECRET SECRET_KEY
ENV ACCESS_TOKEN SECRET_KEY
ENV YT_URL https://www.youtube.com/feeds/videos.xml?channel_id=0000
ENV POD_URL https://localhost
ENV GIT_URL https://github.com/dftba-club/carl/releases.atom
ENV GIT_MSG='A new version of me has been released! Please update me!'
ENV DELAY 10

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Do all of this work as ROOT
USER root

# Create User
RUN adduser ${USER} --system --no-create-home

# update the package repository and install packages
#RUN apk update && apk add py3-pip

# Install Mastodon API
RUN pip3 install Mastodon.py
RUN pip3 install feedparser

# Copy in the startup script & bot script
COPY bot.py .

# Set user during the container runtime
USER ${USER}
# Let's go!
CMD [ "python", "/app/bot.py" ]