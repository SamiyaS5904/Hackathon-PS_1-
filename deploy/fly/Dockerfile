# Timetabl.ai backend + assistant in one container (Fly.io; built from the repository root, see fly.toml).
# The backend answers on $PORT and passes /assistant/... to the assistant on 127.0.0.1:8001.
FROM python:3.12-slim

RUN useradd -m -u 1000 user
WORKDIR /home/user/app

COPY --chown=user backend/requirements.txt backend/requirements.txt
COPY --chown=user chatbot/requirements.txt chatbot/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt -r chatbot/requirements.txt

COPY --chown=user backend backend
COPY --chown=user chatbot chatbot
COPY --chown=user deploy/hf-space/start.sh start.sh

USER user
ENV PYTHONUNBUFFERED=1 \
    ASSISTANT_URL=http://127.0.0.1:8001 \
    PORT=8080
EXPOSE 8080
CMD ["bash", "start.sh"]
