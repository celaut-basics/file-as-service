FROM debian:trixie-slim@sha256:d7e12182ce18b85b93007c1dedf31f2d29e01ccf3182cc4017c709b6259bc132
RUN apt-get update && apt-get install -y --no-install-recommends python3 mupdf-tools && rm -rf /var/lib/apt/lists/*
COPY ./service /service
RUN chmod -R a+rX /service && chmod 755 /service/entrypoint.sh
ENTRYPOINT ["/service/entrypoint.sh"]
