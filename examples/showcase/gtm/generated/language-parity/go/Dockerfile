FROM golang:1.25

WORKDIR /repo

COPY packages/go /repo/packages/go
COPY examples/showcase/gtm/generated/language-parity/go /repo/examples/showcase/gtm/generated/language-parity/go

WORKDIR /repo/examples/showcase/gtm/generated/language-parity/go

RUN go build -o /usr/local/bin/gtm-go-native .

EXPOSE 4100

CMD ["/usr/local/bin/gtm-go-native"]
