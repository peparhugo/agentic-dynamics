import { describe, it, expect, afterEach } from "vitest";
import path from "node:path";
import { injectReloadScript, resolveRequestPath, serve, RELOAD_SCRIPT, type DevServer } from "../src/server.js";
import type { SiteConfig } from "../src/types.js";
import { makeTmpDir, writeTree, BASIC_TEMPLATES } from "./helpers.js";

describe("injectReloadScript", () => {
  it("injects before </body> when present", () => {
    const out = injectReloadScript("<html><body><p>x</p></body></html>");
    expect(out).toContain(RELOAD_SCRIPT);
    expect(out.indexOf(RELOAD_SCRIPT)).toBeLessThan(out.indexOf("</body>"));
  });

  it("appends when no </body> exists", () => {
    const out = injectReloadScript("<p>fragment</p>");
    expect(out.endsWith(RELOAD_SCRIPT)).toBe(true);
  });
});

describe("resolveRequestPath", () => {
  it("serves directory index.html and blocks traversal", () => {
    const root = makeTmpDir();
    writeTree(root, { "index.html": "home", "a/index.html": "a", "a/x.css": "css" });
    expect(resolveRequestPath(root, "/")).toBe(path.join(root, "index.html"));
    expect(resolveRequestPath(root, "/a/")).toBe(path.join(root, "a", "index.html"));
    expect(resolveRequestPath(root, "/a/x.css")).toBe(path.join(root, "a", "x.css"));
    expect(resolveRequestPath(root, "/missing")).toBeNull();
    expect(resolveRequestPath(root, "/../../etc/passwd")).toBeNull();
    expect(resolveRequestPath(root, "/%2e%2e/%2e%2e/etc/passwd")).toBeNull();
  });
});

describe("dev server (integration)", () => {
  let server: DevServer | undefined;

  afterEach(async () => {
    await server?.close();
    server = undefined;
  });

  it("builds, serves HTML with the reload script injected, and 404s unknown paths", async () => {
    const root = makeTmpDir();
    const site: SiteConfig = {
      sourceDir: path.join(root, "content"),
      templateDir: path.join(root, "templates"),
      outDir: path.join(root, "out"),
      baseUrl: "http://localhost",
      title: "Dev",
      includeDrafts: false,
    };
    writeTree(site.templateDir, BASIC_TEMPLATES);
    writeTree(site.sourceDir, { "hi.md": `---\ntitle: Hi\ndate: 2024-01-01\n---\nHello dev` });

    server = await serve(site, 0);
    const base = `http://localhost:${server.port}`;

    const home = await fetch(`${base}/`);
    expect(home.status).toBe(200);
    expect(home.headers.get("content-type")).toContain("text/html");
    const html = await home.text();
    expect(html).toContain("Hello dev");
    expect(html).toContain("__livereload");

    const rss = await fetch(`${base}/rss.xml`);
    expect(rss.status).toBe(200);
    expect(await rss.text()).not.toContain("__livereload");

    const missing = await fetch(`${base}/nope`);
    expect(missing.status).toBe(404);
  });
});
