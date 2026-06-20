FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install chromium

# Copy application files
COPY . .

# Expose port (Render injects PORT)
EXPOSE 8000

# Start FastAPI app, listening on PORT env var
CMD python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
