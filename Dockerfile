FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Start FastAPI app, listening on PORT env var (injected by Render)
CMD python3 -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
