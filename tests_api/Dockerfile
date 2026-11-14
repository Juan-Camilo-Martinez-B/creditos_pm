FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /tests
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY esquemas.py test_contrato_api.py ./
CMD ["pytest", "-v", "--tb=short", "test_contrato_api.py"]
