import { describe, it, expect, beforeAll, afterAll } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { WebSocket } from "ws";
import { injectReloadScript, RELOAD_SCRIPT, startDevServer, type DevServer } from "../src/server.js";
import type { SiteConfig } from "../src/types.js";

describe("injectReloadScript", () => {
  it("injects before </body>", () => {
    const out = injectReloadScript("<html><body><p>x</p></body></html>");
    expect(out).toContain(RELOAD_SCRIPT);
    expect(out.indexOf(RELOAD_SCRIPT)).toBeLessThan(out.indexOf("</body>"));
  });

  it("appends when </body> is missing", () => {
    const out = injectReloadScript("<p>x</p>");
    expect(out.endsWith(RELOAD_SCRIPT)).toBe(true);
  });
});

describe("dev server", () => {
  let root: string;
  let server: DevServer;
  let config: SiteConfig;

  beforeAll(async () => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-srv-"));
    fs.mkdirSync(path.join(root, "content"), { recursive: true });
    fs.writeFileSync(
      path.join(root, "content", "a.md"),
      `---\ntitle: A\ndate: 2024-01-01\n---\nhello world`
    );
    config = {
      sourceDir: path.join(root, "content"),
      templateDir: path.join(root, "templates"),
      outDir: path.join(root, "out"),
      baseUrl: "http://localhost",
      siteTitle: "S",
      siteDescription: "",
      includeDrafts: false,
    };
    server = await startDevServer(config, 0); // ephemeral port
  }, 15000);

  afterAll(async () => {
    await server.close();
    fs.rmSync(root, { recursive: true, force: true });
  });

  it("serves built pages with the reload script injected", async () => {
    const res = await fetch(`http://localhost:${server.port}/a/`);
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("hello world");
    expect(html).toContain("__livereload");
  });

  it("serves feed.xml without injection", async () => {
    const res = await fetch(`http://localhost:${server.port}/feed.xml`);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("xml");
    expect(await res.text()).not.toContain("__livereload");
  });

  it("returns 404 with reload script for missing paths", async () => {
    const res = await fetch(`http://localhost:${server.port}/nope/`);
    expect(res.status).toBe(404);
    expect(await res.text()).toContain("__livereload");
  });

  it("broadcasts reload over WebSocket when a source file changes", async () => {
    const ws = new WebSocket(`ws://localhost:${server.port}/__livereload`);
    await new Promise<void>((resolve, reject) => {
      ws.on("open", resolve);
      ws.on("error", reject);
    });
    const reload = new Promise<string>((resolve) =>
      ws.on("message", (data) => resolve(data.toString()))
    );
    fs.writeFileSync(
      path.join(config.sourceDir, "a.md"),
      `---\ntitle: A\ndate: 2024-01-01\n---\nhello again`
    );
    expect(await reload).toBe("reload");
    ws.close();

    const html = await (await fetch(`http://localhost:${server.port}/a/`)).text();
    expect(html).toContain("hello again");
  }, 15000);
});
