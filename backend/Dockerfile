FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl xz-utils fontconfig \
    && rm -rf /var/lib/apt/lists/*

ARG TYPST_VERSION=v0.15.0
RUN curl -sSL "https://github.com/typst/typst/releases/download/${TYPST_VERSION}/typst-x86_64-unknown-linux-musl.tar.xz" \
    | tar -xJ --strip-components=1 -C /usr/local/bin "typst-x86_64-unknown-linux-musl/typst"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY templates ./templates
COPY fonts /usr/share/fonts/truetype/tandoor2typst
RUN fc-cache -f

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
