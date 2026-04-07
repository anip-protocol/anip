/**
 * Vue plugin for providing an ANIPClient to the component tree.
 *
 * Usage:
 *   import { createAnipPlugin } from '@anip-dev/vue'
 *   app.use(createAnipPlugin('https://api.example.com'))
 */

import { type App, type InjectionKey } from "vue";
import { ANIPClient } from "@anip-dev/client";
import type { ANIPClientOptions } from "@anip-dev/client";

export const AnipClientKey: InjectionKey<ANIPClient> = Symbol("AnipClient");

export function createAnipPlugin(
  baseUrl: string,
  opts?: ANIPClientOptions,
) {
  const client = new ANIPClient(baseUrl, opts);
  return {
    install(app: App) {
      app.provide(AnipClientKey, client);
    },
  };
}
