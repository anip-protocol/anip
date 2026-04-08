/**
 * Angular injection tokens for ANIP configuration.
 *
 * Usage:
 *   providers: [
 *     { provide: ANIP_BASE_URL, useValue: 'https://api.example.com' },
 *     { provide: ANIP_TIMEOUT, useValue: 30000 },
 *   ]
 */

import { InjectionToken } from "@angular/core";

/** Injection token for the ANIP service base URL. */
export const ANIP_BASE_URL = new InjectionToken<string>("ANIP_BASE_URL");

/** Optional injection token for request timeout in milliseconds. */
export const ANIP_TIMEOUT = new InjectionToken<number>("ANIP_TIMEOUT");
