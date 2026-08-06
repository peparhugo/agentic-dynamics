import { describe, it, expect, beforeAll, afterAll } from "vitest";
import fs from "node:fs/promises";
import path from "node:path";
import WebSocket from "ws";
import { serve, injectReloadScript, RELOAD_SNIPPET, LIVE_RELOAD_PATH, type DevServer } from "../src/server.js";
import { makeFixture, type Fixture } from "./helpers.js";

describe("injectReloadScript", () => {
  it("injects before </body> when present", () => {
    const out = injectReloadScript("<html><body><p>x</p></body></html>");
    expect(out).toContain(RELOAD_SNIPPET);
    expect(out.indexOf(RELOAD_SNIPPET)).toBeLessThan(out.indexOf("</body>"));
  });

  it("appends when </body> is absent", () => {
    const out = injectReloadScript("<p>x</p>");
    expect(out.endsWith(RELOAD_SNIPPET)).toBe(true);
  });
});

describe("dev server", () => {
  let fixture: Fixture;
  let server: DevServer;

  beforeAll(async () => {
    fixture = await makeFixture();
    server = await serve({
      sourceDir: fixture.sourceDir,
      templateDir: fixture.templateDir,
      outDir: fixture.outDir,
      port: 0, // OS-assigned port
    });
  }, 20000);

  afterAll(async () => {
    await server.close();
    await fixture.cleanup();
  });

  it("serves built pages with the reload script injected", async () => {
    const res = await fetch(`http://127.0.0.1:${server.port}/posts/hello/`);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/html");
    const html = await res.text();
    expect(html).toContain("Hello World");
    expect(html).toContain(LIVE_RELOAD_PATH);
  });

  it("serves non-HTML assets without injection", async () => {
    const res = await fetch(`http://127.0.0.1:${server.port}/style.css`);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/css");
    const css = await res.text();
    expect(css).toContain("font-family");
    expect(css).not.toContain(LIVE_RELOAD_PATH);
  });

  it("returns 404 for missing paths", async () => {
    const res = await fetch(`http://127.0.0.1:${server.port}/nope/`);
    expect(res.status).toBe(404);
  });

  it("broadcasts reload over WebSocket when a source file changes", async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${server.port}${LIVE_RELOAD_PATH}`);
    await new Promise<void>((resolve, reject) => {
      ws.once("open", () => resolve());
      ws.once("error", reject);
    });

    const reload = new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("no reload message")), 15000);
      ws.on("message", (data) => {
        clearTimeout(timer);
        resolve(data.toString());
      });
    });

    // Trigger a rebuild
    await fs.writeFile(
      path.join(fixture.sourceDir, "posts", "hello.md"),
      "---\ntitle: Hello World\ndate: 2026-01-15\n---\nEdited!\n"
    );

    expect(await reload).toBe("reload");
    ws.close();

    // The rebuilt page reflects the edit
    const html = await (await fetch(`http://127.0.0.1:${server.port}/posts/hello/`)).text();
    expect(html).toContain("Edited!");
  }, 20000);
});
