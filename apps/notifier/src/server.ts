import path from "node:path";
import * as grpc from "@grpc/grpc-js";
import * as protoLoader from "@grpc/proto-loader";
import { createApiClient } from "./apiClient";
import { config } from "./config";
import { handleClassifyTicket, handleDraftReply, type TicketRequest } from "./handlers";
import { createRedisPublisher } from "./redisPublisher";

const PROTO_PATH = path.resolve(__dirname, "../../../proto/ticket.proto");

function loadTicketAgentService() {
  const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
    keepCase: true,
    longs: String,
    enums: String,
    defaults: true,
    oneofs: true,
  });
  const proto = grpc.loadPackageDefinition(packageDefinition) as unknown as {
    supportpilot: { TicketAgent: grpc.ServiceClientConstructor };
  };
  return proto.supportpilot.TicketAgent.service;
}

export function buildServer(): grpc.Server {
  const publisher = createRedisPublisher();
  const apiClient = createApiClient();
  const deps = { publisher, apiClient };

  const server = new grpc.Server();
  server.addService(loadTicketAgentService(), {
    ClassifyTicket: (
      call: grpc.ServerUnaryCall<TicketRequest, unknown>,
      callback: grpc.sendUnaryData<unknown>,
    ) => {
      handleClassifyTicket(call.request, deps)
        .then((response) => callback(null, response))
        .catch((err: Error) => callback({ code: grpc.status.INTERNAL, message: err.message }, null));
    },
    DraftReply: (
      call: grpc.ServerUnaryCall<TicketRequest, unknown>,
      callback: grpc.sendUnaryData<unknown>,
    ) => {
      handleDraftReply(call.request, deps)
        .then((response) => callback(null, response))
        .catch((err: Error) => callback({ code: grpc.status.INTERNAL, message: err.message }, null));
    },
  });

  return server;
}

function main() {
  const server = buildServer();
  const address = `0.0.0.0:${config.grpcPort}`;
  server.bindAsync(address, grpc.ServerCredentials.createInsecure(), (err, port) => {
    if (err) {
      console.error("failed to bind gRPC server:", err);
      process.exit(1);
    }
    console.log(`notifier gRPC server listening on ${address} (bound port ${port})`);
  });
}

if (require.main === module) {
  main();
}
