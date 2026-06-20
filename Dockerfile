FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Temporary diagnostic CMD to debug paths
CMD python3 -c "import sys; print('Executable:', sys.executable); print('Path:', sys.path); import os; print('ENV:', os.environ); import subprocess; print('Python3 which:', subprocess.run(['which', 'python3'], capture_output=True).stdout.decode()); print('Pip list:', subprocess.run(['python3', '-m', 'pip', 'list'], capture_output=True).stdout.decode())"
