# PDF reader of ScoreMaster for a private Hugging Face Space (Docker SDK, port 7860). Everything is pinned to what the
# feasibility test of 2026-10-27 measured: copisteria at its commit, the copista-2m weights at their revision, PyTorch
# for CPU. The build context is the Space repository made by scripts/deploy_omr_space.sh (this file at its root and
# the omr/ package beside it).
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
COPY omr/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

ARG COPISTERIA_COMMIT=5d1cd54286bb8a27e33a495c88fadf0e2101152d
ARG COPISTA_REVISION=c37d89e1e52edc95c1a73bda0aea5f2f71a9c763
RUN git clone https://github.com/kobimusic/copisteria /opt/copisteria \
    && git -C /opt/copisteria checkout "$COPISTERIA_COMMIT" \
    && pip install --no-cache-dir --no-deps -e /opt/copisteria
# copisteria looks for its weights in models/ of its own folder.
RUN python -c "from huggingface_hub import hf_hub_download as get; \
[get('kobimusic/copista-2m', name, revision='$COPISTA_REVISION', local_dir='/opt/copisteria/models') \
 for name in ('evidence-2m.pt', 'small/v7_obj-recall_best.pt')]"

WORKDIR /app
COPY omr ./omr
# Hugging Face runs Spaces as user 1000; the reader never runs as root.
RUN useradd --system --uid 1000 --no-create-home omr && chown -R omr /opt/copisteria
USER omr
ENV COPISTERIA_DIR=/opt/copisteria HOME=/tmp PYTHONDONTWRITEBYTECODE=1
EXPOSE 7860
CMD ["uvicorn", "omr.app:app", "--host", "0.0.0.0", "--port", "7860"]
