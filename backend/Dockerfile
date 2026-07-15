FROM python:3.12-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /workspace

# Install system dependencies for build compiling
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source files
COPY . .

# Create persistent directories and ensure permissions
RUN mkdir -p uploads chroma_db logs

# Create a non-privileged user and group for runtime security
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -d /workspace -s /bin/false appuser && \
    chown -R appuser:appgroup /workspace

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
