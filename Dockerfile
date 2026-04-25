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
    && rm -rf /var/lib/apt/lists/*

# ── App setup ─────────────────────────────────────────────────────────────────
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create data directories
RUN mkdir -p data/guilds

# ── Run ───────────────────────────────────────────────────────────────────────
CMD ["python", "main.py"]
