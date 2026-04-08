/**
 * React context provider for ANIPClient.
 *
 * Usage:
 *   import { AnipProvider } from '@anip-dev/react'
 *
 *   <AnipProvider baseUrl="https://api.example.com">
 *     <App />
 *   </AnipProvider>
 */

import React, { createContext, useContext, useRef } from "react";
import { ANIPClient } from "@anip-dev/client";
import type { ANIPClientOptions } from "@anip-dev/client";

export const AnipClientContext = createContext<ANIPClient | null>(null);

export interface AnipProviderProps {
  baseUrl: string;
  children: React.ReactNode;
  timeout?: number;
}

export function AnipProvider({
  baseUrl,
  children,
  timeout,
}: AnipProviderProps): React.JSX.Element {
  const clientRef = useRef<ANIPClient | null>(null);

  if (!clientRef.current) {
    const opts: ANIPClientOptions | undefined = timeout
      ? { timeout }
      : undefined;
    clientRef.current = new ANIPClient(baseUrl, opts);
  }

  // Keep base URL in sync when prop changes.
  clientRef.current.setBaseUrl(baseUrl);

  return (
    <AnipClientContext.Provider value={clientRef.current}>
      {children}
    </AnipClientContext.Provider>
  );
}

/**
 * Internal helper — returns the ANIPClient from context or throws.
 */
export function useAnipClientInternal(): ANIPClient {
  const client = useContext(AnipClientContext);
  if (!client) {
    throw new Error(
      "ANIPClient not provided. Wrap your component tree in <AnipProvider>.",
    );
  }
  return client;
}
