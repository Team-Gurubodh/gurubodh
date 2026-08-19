FROM node:22-bookworm-slim AS node-runtime

FROM python:3.12-slim-bookworm

ARG SOURCE_REVISION=unknown
ARG IMAGE_VERSION=dev
ARG IMAGE_CREATED=unknown

LABEL org.opencontainers.image.source="https://github.com/Team-Gurubodh/gurubodh" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.version="${IMAGE_VERSION}" \
      org.opencontainers.image.created="${IMAGE_CREATED}" \
      org.opencontainers.image.title="gurubodh-cli"

# Node is required by the bundled APS legacy-font converter.  No GPU runtime or
# model files are included: model snapshots live in the mounted cache volume.
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
RUN groupadd --gid 10001 gurubodh \
    && useradd --uid 10001 --gid gurubodh --create-home --shell /usr/sbin/nologin gurubodh \
    && install -d --owner=gurubodh --group=gurubodh /work /var/cache/gurubodh/models

WORKDIR /opt/gurubodh-cli
COPY --chown=gurubodh:gurubodh . .
RUN printf '{\n  "source_revision": "%s",\n  "image_revision": "%s",\n  "image_version": "%s",\n  "image_created": "%s"\n}\n' \
      "$SOURCE_REVISION" "$SOURCE_REVISION" "$IMAGE_VERSION" "$IMAGE_CREATED" \
      > /opt/gurubodh-cli/gurubodh/build_provenance.json
# Install Torch from its CPU-only index first. The CLI dependency permits this
# compatible version, so the subsequent package install does not pull CUDA
# libraries into a CPU runner image.
RUN python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 \
    && python -m pip install --no-cache-dir .

ENV GURUBODH_CLI_ROOT=/opt/gurubodh-cli \
    GURUBODH_BUILD_PROVENANCE_FILE=/opt/gurubodh-cli/gurubodh/build_provenance.json \
    GURUBODH_MODEL_CACHE_DIR=/var/cache/gurubodh/models \
    HF_HOME=/var/cache/gurubodh/models \
    TOKENIZERS_PARALLELISM=false
USER gurubodh
WORKDIR /work
ENTRYPOINT ["gurubodh"]
CMD ["--help"]
