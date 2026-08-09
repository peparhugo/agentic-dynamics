import { customAlphabet } from "nanoid";
import { insertUrl, getByCode } from "./db.js";

const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
const CODE_LENGTH = 7;
const MAX_RETRIES = 5;

const generate = customAlphabet(ALPHABET, CODE_LENGTH);

export function generateCode(): string {
  return generate();
}

export function shorten(original_url: string, expiresInSeconds: number | null): string {
  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    const code = generateCode();
    const existing = getByCode(code);
    if (existing) continue;

    const expires_at = expiresInSeconds ? Math.floor(Date.now() / 1000) + expiresInSeconds : null;
    insertUrl(code, original_url, expires_at);
    return code;
  }
  throw new Error("Failed to generate a unique short code after max retries");
}
