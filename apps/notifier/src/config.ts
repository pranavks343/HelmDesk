export const config = {
  grpcPort: process.env.GRPC_PORT ?? "50051",
  redisUrl: process.env.REDIS_URL ?? "redis://localhost:6379/0",
  apiInternalBaseUrl: process.env.API_INTERNAL_BASE_URL ?? "http://localhost:8000",
  internalServiceToken: process.env.INTERNAL_SERVICE_TOKEN ?? "dev-internal-token-change-me",
};
