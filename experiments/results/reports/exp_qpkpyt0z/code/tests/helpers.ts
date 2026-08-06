import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { SiteConfig } from "../src/types.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

export const fixturesDir = resolve(__dirname, "fixtures");

export function makeConfig(overrides?: Partial<SiteConfig>): SiteConfig {
  return {
    sourceDir: resolve(fixturesDir, "content"),
    templateDir: resolve(fixturesDir, "templates"),
    outputDir: resolve(fixturesDir, "output"),
    siteTitle: "Test Site",
    siteUrl: "http://localhost:3000",
    postsPerPage: 10,
    ...overrides,
  };
}
