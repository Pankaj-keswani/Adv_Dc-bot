# ── Stage 1: FFmpeg + Python base ────────────────────────────────────────────
FROM python:3.11-slim

# Install system dependencies (FFmpeg required for music)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    libopus-dev \
    libffi-dev \
    libnacl-dev \
    build-essential \
    python3-dev \
    git \
    curl \
    fonts-liberation \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── App setup ─────────────────────────────────────────────────────────────────
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create data directories and set permissions for Hugging Face (UID 1000)
RUN mkdir -p data/guilds && chmod -R 777 data

# ── Run ───────────────────────────────────────────────────────────────────────
CMD ["python", "main.py"]
