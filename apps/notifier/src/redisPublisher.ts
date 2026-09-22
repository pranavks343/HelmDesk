import { createClient, type RedisClientType } from "redis";
import { config } from "./config";

export const CHANNEL_TICKET_UPDATED = "ticket.updated";
export const CHANNEL_TICKET_MESSAGE = "ticket.message";

export interface RedisPublisher {
  publish(channel: string, payload: unknown): Promise<void>;
  quit(): Promise<void>;
}

export function createRedisPublisher(url: string = config.redisUrl): RedisPublisher {
  const client: RedisClientType = createClient({ url });
  let connected = false;

  async function ensureConnected() {
    if (!connected) {
      await client.connect();
      connected = true;
    }
  }

  return {
    async publish(channel: string, payload: unknown) {
      await ensureConnected();
      await client.publish(channel, JSON.stringify(payload));
    },
    async quit() {
      if (connected) {
        await client.quit();
        connected = false;
      }
    },
  };
}
