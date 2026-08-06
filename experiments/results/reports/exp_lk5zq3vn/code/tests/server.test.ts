import { describe, it, expect, beforeAll, afterAll } from "vitest";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { injectReloadScript, RELOAD_SNIPPET, startDevServer } from "../src/server.js";
import type { SiteConfig } from "../src/types.js";
import type { DevServer } from "../src/server.js";
import WebSocket from "ws";

describe("injectReloadScript", () => {
  it("injects before </body>", () => {
    const out = injectReloadScript("<html><body><p>x</p></body></html>");
    expect(out.indexOf(RELOAD_SNIPPET)).toBeLessThan(out.indexOf("</body>"));
    expect(out).toContain("__livereload");
  });

  it("appends when no </body> exists", () => {
    expect(injectReloadScript("<p>x</p>")).toBe("<p>x</p>" + RELOAD_SNIPPET);
  });
});

describe("dev server", () => {
  let root: string;
  let server: DevServer;
  let config: SiteConfig;

  beforeAll(async () => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), "ssgen-srv-"));
    config = {
      sourceDir: path.join(root, "content"),
      templateDir: path.join(root, "templates"),
      outDir: path.join(root, "out"),
      includeDrafts: false,
      baseUrl: "http://localhost",
      siteTitle: "S",
      siteDescription: "",
    };
    fs.mkdirSync(config.sourceDir, { recursive: true });
    fs.mkdirSync(config.templateDir, { recursive: true });
    fs.writeFileSync(path.join(config.templateDir, "default.hbs"), `<html><body>{{{content}}}</body></html>`);
    fs.writeFileSync(path.join(config.sourceDir, "a.md"), `---\ntitle: A\ndate: 2026-01-01\n---\nHello A`);
    server = await startDevServer(config, 0); // ephemeral port
  }, 15000);

  afterAll(async () => {
    await server?.close();
    fs.rmSync(root, { recursive: true, force: true });
  });

  it("serves built HTML with the reload script injected", async () => {
    const res = await fetch(`http://localhost:${server.port}/a.html`);
    expect(res.status).toBe(200);
    const body = await res.text();
    expect(body).toContain("Hello A");
    expect(body).toContain("__livereload");
  });

  it("404s unknown paths (with reload script so the page can recover)", async () => {
    const res = await fetch(`http://localhost:${server.port}/nope.html`);
    expect(res.status).toBe(404);
    expect(await res.text()).toContain("__livereload");
  });

  it("broadcasts reload over WebSocket when a source file changes", async () => {
    const ws = new WebSocket(`ws://localhost:${server.port}/__livereload`);
    await new Promise((resolve, reject) => {
      ws.once("open", resolve);
      ws.once("error", reject);
    });
    const msg = new Promise<string>((resolve, reject) => {
      const t = setTimeout(() => reject(new Error("no reload message within 10s")), 10000);
      ws.once("message", (d) => {
        clearTimeout(t);
        resolve(d.toString());
      });
    });
    fs.writeFileSync(path.join(config.sourceDir, "a.md"), `---\ntitle: A\ndate: 2026-01-01\n---\nHello EDITED`);
    expect(await msg).toBe("reload");
    ws.close();

    // rebuilt content is served
    const body = await (await fetch(`http://localhost:${server.port}/a.html`)).text();
    expect(body).toContain("Hello EDITED");
  }, 15000);
});
