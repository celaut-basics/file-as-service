FROM debian:trixie-slim@sha256:d7e12182ce18b85b93007c1dedf31f2d29e01ccf3182cc4017c709b6259bc132 AS decoder
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl ca-certificates xz-utils && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN curl -fsSL https://ffmpeg.org/releases/ffmpeg-8.0.1.tar.xz -o ffmpeg.tar.xz \
 && echo '05ee0b03119b45c0bdb4df654b96802e909e0a752f72e4fe3794f487229e5a41  ffmpeg.tar.xz' | sha256sum -c - \
 && tar -xf ffmpeg.tar.xz
WORKDIR /src/ffmpeg-8.0.1
# Only H.264/AAC input and raw RGB/PCM output. No muxed source is forwarded.
RUN ./configure --disable-everything --disable-doc --disable-debug --disable-network --disable-autodetect \
 --disable-x86asm --enable-ffmpeg --enable-protocol=file,pipe --enable-demuxer=mov \
 --enable-parser=h264,aac --enable-decoder=h264,aac --enable-encoder=rawvideo,pcm_f32le \
 --enable-muxer=rawvideo,pcm_f32le --enable-filter=scale,pad,fps,format,aformat,aresample,anull,null \
 --enable-swscale --enable-swresample --extra-cflags='-O2 -ffile-prefix-map=/src=.' \
 && make -j4 && strip ffmpeg
FROM debian:trixie-slim@sha256:d7e12182ce18b85b93007c1dedf31f2d29e01ccf3182cc4017c709b6259bc132
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
COPY --from=decoder /src/ffmpeg-8.0.1/ffmpeg /usr/local/bin/ffmpeg
COPY ./service /service
RUN chmod -R a+rX /service && chmod 755 /service/entrypoint.sh
ENTRYPOINT ["/service/entrypoint.sh"]
