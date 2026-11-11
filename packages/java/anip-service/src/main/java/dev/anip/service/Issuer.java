package dev.anip.service;

/**
 * Identifies who is asking for a token and how they proved it.
 *
 * @param principal the authenticated caller
 * @param viaToken  true when the caller authenticated with a delegation token
 *                  issued by this service rather than with a bootstrap credential
 */
public record Issuer(String principal, boolean viaToken) {
}
