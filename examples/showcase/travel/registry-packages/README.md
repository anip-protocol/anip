# Travel Booking Showcase Registry Package

Generated from `docs/examples/travel-showcase/source-spec.md`.

Generate Python code:

```bash
cd packages/go
go run ./cmd/anip-generate \
  --package-bundle ../../examples/showcase/travel/registry-packages/travel-booking-showcase-0.1.0.anip-package.json \
  --target python \
  --dependency-source local \
  --package-name anip_travel_showcase \
  --port 9110 \
  --output ../../examples/showcase/travel/generated/studio_travel \
  --force
```
