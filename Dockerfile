# Use a multi-stage build to reduce final image size
FROM python:3.9-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only what's needed for installing dependencies
COPY requirements.txt .

# Install Python dependencies
RUN pip install --user -r requirements.txt

# Runtime stage
FROM python:3.9-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libasound2 \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application files from local directory
COPY home-assistant-mqtt-volume-control.py .
COPY configuration.yaml .

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Volume for configuration (if you want to mount it at runtime instead)
VOLUME /app/config

# Set the entrypoint to your specific script
ENTRYPOINT ["python", "home-assistant-mqtt-volume-control.py"]