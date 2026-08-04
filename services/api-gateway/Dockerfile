FROM golang:1.22-alpine AS builder

WORKDIR /app

ENV GOPROXY=https://goproxy.cn,direct

RUN apk add --no-cache git

COPY go.mod ./
COPY go.sum* ./
RUN go mod download 2>/dev/null || go mod tidy
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 go build -o /api-gateway ./cmd/server

FROM alpine:3.19
RUN apk add --no-cache ca-certificates curl
COPY --from=builder /api-gateway /usr/local/bin/api-gateway
EXPOSE 8080 8081
CMD ["api-gateway"]
