FROM python:3.12-slim
WORKDIR /srv
# Optional LLM agents: docker build --build-arg INSTALL_LLM=1 -t holdem .
ARG INSTALL_LLM=0
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$INSTALL_LLM" = "1" ]; then pip install --no-cache-dir langchain-openai; fi
COPY app ./app
COPY static ./static
RUN useradd -m player
USER player
ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import os,urllib.request as u;u.urlopen('http://localhost:'+os.environ.get('PORT','8000')+'/health')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
