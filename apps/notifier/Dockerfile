# Build context is the repo root (see infra/docker-compose.yml) - notifier loads
# ../../../proto/ticket.proto relative to dist/server.js at runtime (dynamic @grpc/proto-loader,
# no codegen step), so the container's directory layout has to mirror the repo's.
FROM node:22-slim AS build
WORKDIR /repo/apps/notifier
COPY apps/notifier/package.json apps/notifier/package-lock.json ./
RUN npm ci
COPY apps/notifier .
RUN npm run build

FROM node:22-slim
WORKDIR /repo/apps/notifier
COPY apps/notifier/package.json apps/notifier/package-lock.json ./
RUN npm ci --omit=dev
COPY --from=build /repo/apps/notifier/dist ./dist
COPY proto /repo/proto

EXPOSE 50051
CMD ["node", "dist/server.js"]
