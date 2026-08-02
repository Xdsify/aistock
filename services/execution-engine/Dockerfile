FROM golang:1.22-alpine AS builder

WORKDIR /app

RUN apk add --no-cache git

COPY go.mod ./
COPY go.sum* ./
RUN go mod download 2>/dev/null || go mod tidy
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 go build -o /execution-engine ./cmd/server

FROM alpine:3.19
RUN apk add --no-cache ca-certificates curl
COPY --from=builder /execution-engine /usr/local/bin/execution-engine
EXPOSE 9001
CMD ["execution-engine"]
