# Stage 1: Build the frontend (js bundle and css styles)
FROM node:24-slim AS builder
WORKDIR /app

# Copy dependency files first for caching
COPY static/js/package.json static/js/package-lock.json* ./static/js/

# Install dependencies
RUN cd static/js && npm install

# Copy source files needed for build
COPY static/js/ ./static/js/
COPY static/css/ ./static/css/

# Build assets (compiles SCSS to CSS and runs Webpack)
RUN cd static/js && npm run build

# Stage 2: Final application image
FROM ubuntu:22.04
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# Install system dependencies (including git for git+ requirements and python3-pip)
RUN apt-get update && apt-get -y install \
    python3-pip \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /rsstag

# Python dependencies
COPY requirements.txt /rsstag/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy all application code
COPY . /rsstag

# Copy built frontend assets from the builder stage
# This ensures we have the latest built versions and overwrites any existing ones
COPY --from=builder /app/static/js/bundle.js /rsstag/static/js/
COPY --from=builder /app/static/js/bundle.js.map /rsstag/static/js/
COPY --from=builder /app/static/css/style.css /rsstag/static/css/
COPY --from=builder /app/static/css/style.css.map /rsstag/static/css/

EXPOSE 8885
CMD python3 worker.py & python3 web.py

