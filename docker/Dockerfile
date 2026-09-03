# RazorRecover Dockerfile
# Placeholder - actual stack will be configured later.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "src.razor_recover.main"]
