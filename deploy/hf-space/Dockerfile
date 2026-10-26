# Timetabl.ai backend + assistant in one container (Hugging Face Space, Docker SDK).
# The backend answers on 7860 (the Space's port) and passes /assistant/... to the assistant on 127.0.0.1:8001.
FROM python:3.12-slim

RUN useradd -m -u 1000 user
WORKDIR /home/user/app

COPY --chown=user backend/requirements.txt backend/requirements.txt
COPY --chown=user chatbot/requirements.txt chatbot/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt -r chatbot/requirements.txt

COPY --chown=user backend backend
COPY --chown=user chatbot chatbot
COPY --chown=user start.sh start.sh

USER user
ENV PYTHONUNBUFFERED=1 \
    ASSISTANT_URL=http://127.0.0.1:8001 \
    BACKEND_URL=http://127.0.0.1:7860 \
    SOLVER_WORKERS=4
EXPOSE 7860
CMD ["bash", "start.sh"]
