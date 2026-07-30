FROM golang:1.26.5-alpine3.24 AS build
ARG MINIO_VERSION=RELEASE.2025-10-15T17-29-55Z
RUN CGO_ENABLED=0 go install github.com/minio/minio@${MINIO_VERSION}

FROM alpine:3.24
RUN addgroup -S minio && adduser -S -G minio minio \
    && mkdir -p /data && chown minio:minio /data
COPY --from=build /go/bin/minio /usr/local/bin/minio
USER minio
EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["minio"]
CMD ["server", "/data", "--console-address", ":9001"]
