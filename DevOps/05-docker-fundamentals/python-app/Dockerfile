# Small official Python image
FROM python:3.12-alpine

WORKDIR /app

# Copy requirements first so the dependency layer is cached separately
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY app.py ./

EXPOSE 5000

# -u keeps stdout unbuffered so logs appear immediately in `docker logs`
CMD ["python", "-u", "app.py"]
