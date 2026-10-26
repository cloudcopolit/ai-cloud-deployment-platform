# Egress proxy for the deploy runner (ADR-026): the runner's only way out, and it only
# reaches AWS endpoints (*.amazonaws.com). Everything else is refused.
FROM alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc
RUN apk add --no-cache tinyproxy=1.11.2-r0
COPY tinyproxy.conf /etc/tinyproxy/tinyproxy.conf
COPY allowlist /etc/tinyproxy/allowlist
USER nobody
EXPOSE 3128
CMD ["tinyproxy", "-d", "-c", "/etc/tinyproxy/tinyproxy.conf"]
