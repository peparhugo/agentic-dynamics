import chokidar from "chokidar";
import type { SiteConfig } from "./types.js";
import { createDevServer, createReloadBroadcaster } from "./server.js";
import { generateSite, injectReloadScript } from "./generator.js";
import { generateRss } from "./rss.js";
import fs from "node:fs/promises";
import path from "node:path";

export async function watchAndServe(config: SiteConfig): Promise<void> {
  // Initial build with reload script injection
  const { pages } = await generateSite(config);
  await generateRss(config, pages);
  await injectReloadIntoOutput(config.outputDir, config.devServerPort);

  const server = createDevServer2(config.outputDir, config.devServerPort);
  const { broadcast } = createReloadBroadcaster(server);

  server.listen(config.devServerPort, () => {
    console.log(`Dev server: http://localhost:${config.devServerPort}`);
  });

  let rebuilding = false;

  const rebuild = async () => {
    if (rebuilding) return;
    rebuilding = true;
    try {
      const { pages: newPages } = await generateSite(config);
      await generateRss(config, newPages);
      await injectReloadIntoOutput(config.outputDir, config.devServerPort);
      broadcast();
      console.log("Site rebuilt");
    } catch (err) {
      console.error("Rebuild error:", err);
    } finally {
      rebuilding = false;
    }
  };

  const watcher = chokidar.watch(
    [
      path.join(config.sourceDir, "**/*.md"),
      path.join(config.templateDir, "**/*"),
    ],
    { ignoreInitial: true }
  );

  watcher.on("change", rebuild);
  watcher.on("add", rebuild);
  watcher.on("unlink", rebuild);

  process.on("SIGINT", () => {
    watcher.close();
    server.close();
    process.exit(0);
  });
}

async function injectReloadIntoOutput(outputDir: string, port: number): Promise<void> {
  const entries = await fs.readdir(outputDir, { recursive: true });
  for (const entry of entries) {
    const fullPath = path.join(outputDir, entry.toString());
    try {
      const stat = await fs.stat(fullPath);
      if (stat.isFile() && fullPath.endsWith(".html")) {
        let html = await fs.readFile(fullPath, "utf-8");
        if (!html.includes("/__reload")) {
          html = injectReloadScript(html, port);
          await fs.writeFile(fullPath, html, "utf-8");
        }
      }
    } catch {
      // skip
    }
  }
}

// We override the server creation to use the broadcaster pattern
import http from "node:http";

function createDevServer2(outputDir: string, port: number): http.Server {
  const mimeTypes: Record<string, string> = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".xml": "application/xml",
    ".ico": "image/x-icon",
  };

  return http.createServer(async (req, res) => {
    let urlPath = req.url || "/";
    const qIdx = urlPath.indexOf("?");
    if (qIdx !== -1) urlPath = urlPath.slice(0, qIdx);
    if (urlPath === "/") urlPath = "/index.html";

    const filePath = path.join(outputDir, urlPath);
    try {
      const stat = await fs.stat(filePath);
      if (stat.isDirectory()) {
        const indexFile = path.join(filePath, "index.html");
        const content = await fs.readFile(indexFile);
        res.writeHead(200, { "Content-Type": "text/html" });
        res.end(content);
        return;
      }
      const ext = path.extname(filePath).toLowerCase();
      const contentType = mimeTypes[ext] || "application/octet-stream";
      const content = await fs.readFile(filePath);
      res.writeHead(200, { "Content-Type": contentType });
      res.end(content);
    } catch {
      res.writeHead(404);
      res.end("Not Found");
    }
  });
}
