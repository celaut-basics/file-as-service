FROM debian:trixie-slim@sha256:d7e12182ce18b85b93007c1dedf31f2d29e01ccf3182cc4017c709b6259bc132 AS build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && rm -rf /var/lib/apt/lists/*
COPY ./service/chip8.c /src/chip8.c
RUN gcc -std=c11 -O2 -static -s -Wall -Wextra -o /chip8 /src/chip8.c
FROM debian:trixie-slim@sha256:d7e12182ce18b85b93007c1dedf31f2d29e01ccf3182cc4017c709b6259bc132
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
COPY --from=build /chip8 /usr/local/bin/chip8
COPY ./service /service
RUN chmod -R a+rX /service && chmod 755 /service/entrypoint.sh
ENTRYPOINT ["/service/entrypoint.sh"]
