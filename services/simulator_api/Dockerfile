FROM golang:1.24.4-alpine AS dsrnamax-build
WORKDIR /src/vendor/dsrnamax
COPY vendor/dsrnamax/go.mod vendor/dsrnamax/go.sum ./
COPY vendor/dsrnamax/*.go ./
RUN CGO_ENABLED=0 go build -trimpath -o /out/dsrnamax .

FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV DSRNAMAX_BINARY=/usr/local/bin/dsrnamax
WORKDIR /app
COPY services/simulator_api/requirements.lock /app/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /app/requirements.lock
COPY src /app/src
COPY services /app/services
COPY --from=dsrnamax-build /out/dsrnamax /usr/local/bin/dsrnamax
COPY LICENSE THIRD_PARTY_NOTICES.md /app/notices/
COPY docs/LICENSING.md docs/RNA_NN4_PROVENANCE.md /app/notices/docs/
COPY vendor/dsrnamax/LICENSE vendor/dsrnamax/THIRD_PARTY_NOTICES.md /app/notices/dsrnamax/
COPY vendor/licenses/ /app/notices/dependencies/
COPY --from=dsrnamax-build /usr/local/go/LICENSE /app/notices/dependencies/Go-toolchain-LICENSE
EXPOSE 8000
CMD ["python", "-m", "services.simulator_api"]
