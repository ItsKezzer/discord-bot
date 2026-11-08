FROM python:3.11-alpine

# Install build dependencies for C-extensions if needed
RUN apk add --no-cache gcc musl-dev libffi-dev

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "app.py" ]
