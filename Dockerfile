FROM python:3.11-slim

# Create a non-root user
RUN useradd -ms /bin/bash appuser

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O /tmp/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y /tmp/google-chrome-stable_current_amd64.deb \
    && rm /tmp/google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy application files
COPY requirements.txt .
COPY main.py .
COPY utils.py .
COPY downloader/ ./downloader/
COPY Tmp/extension/ ./extension/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Change ownership of app directory
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Set display environment for headless mode
ENV DISPLAY=:99

# Set entrypoint to allow command line arguments
ENTRYPOINT ["python", "main.py"]


# docker run -it --rm -v "%USERPROFILE%\Downloads\Video:/app/Video" downloader:latest