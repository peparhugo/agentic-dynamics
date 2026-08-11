import path from "path";
import { promises as fs } from "fs";
import os from "os";
import http from "http";
import { build } from "../index";
import { startDevServer, injectLiveReloadScript } from "../dev-server";

let testDir: string;

beforeEach(async () => {
  testDir = await fs.mkdtemp(path.join(os.tmpdir(), "ssg-test-"));
});

describe("ssg build", () => {
  test("creates output directory", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out1");

    await build({ contentDir, outputDir: tmpOut });

    const content = await fs.readdir(tmpOut);
    expect(content.length).toBeGreaterThan(0);
  });

  test("generates index.html listing all pages", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out2");

    await build({ contentDir, outputDir: tmpOut });

    const indexHtml = await fs.readFile(
      path.join(tmpOut, "index.html"),
      "utf-8"
    );
    expect(indexHtml).toContain("<title>Site Index</title>");
    expect(indexHtml).toContain("Hello World");
    expect(indexHtml).toContain("About");
    expect(indexHtml).toContain("No Date Page");
  });

  test("index.html lists pages in alphabetical order by path", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out3");

    await build({ contentDir, outputDir: tmpOut });

    const indexHtml = await fs.readFile(
      path.join(tmpOut, "index.html"),
      "utf-8"
    );
    const aboutIdx = indexHtml.indexOf("About");
    const helloIdx = indexHtml.indexOf("Hello World");
    const notagsIdx = indexHtml.indexOf("No Date Page");
    expect(aboutIdx).toBeLessThan(helloIdx);
    expect(helloIdx).toBeLessThan(notagsIdx);
  });

  test("generates individual HTML pages", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out4");

    await build({ contentDir, outputDir: tmpOut });

    const aboutHtml = await fs.readFile(
      path.join(tmpOut, "about.html"),
      "utf-8"
    );
    expect(aboutHtml).toContain("<title>About</title>");
    expect(aboutHtml).toContain("<h2>About This Site</h2>");

    const helloHtml = await fs.readFile(
      path.join(tmpOut, "hello.html"),
      "utf-8"
    );
    expect(helloHtml).toContain("<title>Hello World</title>");
    expect(helloHtml).toContain("<h1>Hello World</h1>");
  });

  test("index.html uses frontmatter as unescaped HTML strings", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out5");

    await build({ contentDir, outputDir: tmpOut });

    const indexHtml = await fs.readFile(
      path.join(tmpOut, "index.html"),
      "utf-8"
    );
    expect(indexHtml).toContain("2024-01-15");
    expect(indexHtml).toContain("Tags: intro, hello");
    expect(indexHtml).toContain("2024-02-20");
    expect(indexHtml).toContain("Tags: meta");
  });

  test("pages with no date/tags omit those sections", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out6");

    await build({ contentDir, outputDir: tmpOut });

    const notagsHtml = await fs.readFile(
      path.join(tmpOut, "notags.html"),
      "utf-8"
    );
    expect(notagsHtml).not.toContain("class=\"date\"");
    expect(notagsHtml).not.toContain("class=\"tags\"");
  });

  test("markdown body is rendered as HTML in page output", async () => {
    const contentDir = path.resolve(__dirname, "..", "..", "content");
    const tmpOut = path.join(testDir, "out7");

    await build({ contentDir, outputDir: tmpOut });

    const aboutHtml = await fs.readFile(
      path.join(tmpOut, "about.html"),
      "utf-8"
    );
    expect(aboutHtml).toContain("<li>Item one</li>");
    expect(aboutHtml).toContain("<li>Item two</li>");
  });

  test("error on missing content directory", async () => {
    const badDir = path.join(testDir, "nonexistent");
    const tmpOut = path.join(testDir, "out8");

    await expect(build({ contentDir: badDir, outputDir: tmpOut })).rejects.toThrow(
      "Content directory not found"
    );
  });

  test("creates subdirectory output for files in subdirectories", async () => {
    const contentDir = path.join(testDir, "content-nested");
    const subDir = path.join(contentDir, "posts");
    await fs.mkdir(subDir, { recursive: true });
    await fs.writeFile(
      path.join(subDir, "nested-post.md"),
      `---
title: Nested Post
---

# Nested

Content in a subdirectory.
`
    );
    await fs.writeFile(
      path.join(contentDir, "root-page.md"),
      `---
title: Root Page
---

# Root

Content at root level.
`
    );

    const tmpOut = path.join(testDir, "out9");
    await build({ contentDir, outputDir: tmpOut });

    const nestedExists = await fs
      .access(path.join(tmpOut, "posts", "nested-post.html"))
      .then(() => true)
      .catch(() => false);
    expect(nestedExists).toBe(true);

    const rootExists = await fs
      .access(path.join(tmpOut, "root-page.html"))
      .then(() => true)
      .catch(() => false);
    expect(rootExists).toBe(true);

    const nestedHtml = await fs.readFile(
      path.join(tmpOut, "posts", "nested-post.html"),
      "utf-8"
    );
    expect(nestedHtml).toContain("<title>Nested Post</title>");

    const indexHtml = await fs.readFile(
      path.join(tmpOut, "index.html"),
      "utf-8"
    );
    expect(indexHtml).toContain("Nested Post");
    expect(indexHtml).toContain("Root Page");
    expect(indexHtml).toContain('href="posts/nested-post.html"');
    expect(indexHtml).toContain('href="root-page.html"');
  });
});

describe("template engine", () => {
  async function setupTemplateContent(
    templatesDir: string,
    contentDir: string,
    templateFiles: Record<string, string>,
    contentFiles: Record<string, string>
  ) {
    for (const [relPath, content] of Object.entries(templateFiles)) {
      const fullPath = path.join(templatesDir, relPath);
      await fs.mkdir(path.dirname(fullPath), { recursive: true });
      await fs.writeFile(fullPath, content, "utf-8");
    }

    for (const [relPath, content] of Object.entries(contentFiles)) {
      const fullPath = path.join(contentDir, relPath);
      await fs.mkdir(path.dirname(fullPath), { recursive: true });
      await fs.writeFile(fullPath, content, "utf-8");
    }
  }

  test("uses default template when no template specified in frontmatter", async () => {
    const templatesDir = path.join(testDir, "templates");
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await setupTemplateContent(
      templatesDir,
      contentDir,
      {
        "default.hbs": `<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{content}}}</body></html>`,
      },
      {
        "page.md": `---
title: My Page
---

# Hello

World
`,
      }
    );

    await build({ contentDir, outputDir, templatesDir });

    const html = await fs.readFile(
      path.join(outputDir, "page.html"),
      "utf-8"
    );
    expect(html).toContain("<title>My Page</title>");
    expect(html).toContain("<h1>Hello</h1>");
    expect(html).toContain("<p>World</p>");
  });

  test("uses custom template from frontmatter template field", async () => {
    const templatesDir = path.join(testDir, "templates");
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await setupTemplateContent(
      templatesDir,
      contentDir,
      {
        "default.hbs": `<html><body>DEFAULT</body></html>`,
        "custom.hbs": `<html><body>CUSTOM: {{title}} {{{content}}}</body></html>`,
      },
      {
        "page.md": `---
title: Special
template: custom
---

# Custom Page
`,
      }
    );

    await build({ contentDir, outputDir, templatesDir });

    const html = await fs.readFile(
      path.join(outputDir, "page.html"),
      "utf-8"
    );
    expect(html).toContain("CUSTOM: Special");
    expect(html).toContain("<h1>Custom Page</h1>");
    expect(html).not.toContain("DEFAULT");
  });

  test("layout template wraps page content with body placeholder", async () => {
    const templatesDir = path.join(testDir, "templates");
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await setupTemplateContent(
      templatesDir,
      contentDir,
      {
        "default.hbs": `<main><h1>{{title}}</h1>{{{content}}}</main>`,
        "layouts/wrapper.hbs": `<html><head><title>{{title}}</title></head><body>WRAPPER_START{{{body}}}WRAPPER_END</body></html>`,
      },
      {
        "page.md": `---
title: Layout Page
layout: wrapper
---

# Content
`,
      }
    );

    await build({ contentDir, outputDir, templatesDir });

    const html = await fs.readFile(
      path.join(outputDir, "page.html"),
      "utf-8"
    );
    expect(html).toContain("WRAPPER_START");
    expect(html).toContain("WRAPPER_END");
    expect(html).toContain("<h1>Layout Page</h1>");
    expect(html).toContain("<h1>Content</h1>");
  });

  test("partials are included in templates", async () => {
    const templatesDir = path.join(testDir, "templates");
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await setupTemplateContent(
      templatesDir,
      contentDir,
      {
        "default.hbs": `<html><body>{{> header}}{{{content}}}{{> footer}}</body></html>`,
        "partials/header.hbs": `<header>SITE HEADER</header>`,
        "partials/footer.hbs": `<footer>SITE FOOTER</footer>`,
      },
      {
        "page.md": `---
title: Partial Test
---

# Page
`,
      }
    );

    await build({ contentDir, outputDir, templatesDir });

    const html = await fs.readFile(
      path.join(outputDir, "page.html"),
      "utf-8"
    );
    expect(html).toContain("<header>SITE HEADER</header>");
    expect(html).toContain("<footer>SITE FOOTER</footer>");
    expect(html).toContain("<h1>Page</h1>");
  });

  test("nav partial is available in layouts", async () => {
    const templatesDir = path.join(testDir, "templates");
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await setupTemplateContent(
      templatesDir,
      contentDir,
      {
        "default.hbs": `<main>{{{content}}}</main>`,
        "layouts/nav-layout.hbs": `<html><body>{{> nav}}{{{body}}}</body></html>`,
        "partials/nav.hbs": `<nav><a href="/">Home</a></nav>`,
      },
      {
        "page.md": `---
title: Nav Test
layout: nav-layout
---

# Nav Page
`,
      }
    );

    await build({ contentDir, outputDir, templatesDir });

    const html = await fs.readFile(
      path.join(outputDir, "page.html"),
      "utf-8"
    );
    expect(html).toContain('<nav><a href="/">Home</a></nav>');
    expect(html).toContain("<h1>Nav Page</h1>");
  });

  test("falls back to inline generation when template directory does not exist", async () => {
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");
    const templatesDir = path.join(testDir, "nonexistent-templates");

    await fs.mkdir(contentDir, { recursive: true });
    await fs.writeFile(
      path.join(contentDir, "page.md"),
      `---
title: Inline Page
---

# Inline Content
`
    );

    await build({ contentDir, outputDir, templatesDir });

    const html = await fs.readFile(
      path.join(outputDir, "page.html"),
      "utf-8"
    );
    expect(html).toContain("<title>Inline Page</title>");
    expect(html).toContain("<h1>Inline Content</h1>");
    expect(html).toContain("<!DOCTYPE html>");
  });

  test("uses index template when index.hbs exists", async () => {
    const templatesDir = path.join(testDir, "templates");
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await setupTemplateContent(
      templatesDir,
      contentDir,
      {
        "default.hbs": `<html><body>{{{content}}}</body></html>`,
        "index.hbs": `<html><body>TEMPLATED INDEX<ul>{{#each pages}}<li>{{title}}</li>{{/each}}</ul></body></html>`,
      },
      {
        "a.md": `---
title: First
---

First page.
`,
        "b.md": `---
title: Second
---

Second page.
`,
      }
    );

    await build({ contentDir, outputDir, templatesDir });

    const indexHtml = await fs.readFile(
      path.join(outputDir, "index.html"),
      "utf-8"
    );
    expect(indexHtml).toContain("TEMPLATED INDEX");
    expect(indexHtml).toContain("<li>First</li>");
    expect(indexHtml).toContain("<li>Second</li>");
  });

  test("template engine handles pages with layout specified in frontmatter", async () => {
    const templatesDir = path.join(testDir, "templates");
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await setupTemplateContent(
      templatesDir,
      contentDir,
      {
        "default.hbs": `<div>CONTENT: {{{content}}}</div>`,
        "layouts/base.hbs": `<html><head><title>{{title}}</title></head><body>LAYOUT:{{{body}}}</body></html>`,
      },
      {
        "page.md": `---
title: Layouted
layout: base
---

# Hello Layout
`,
      }
    );

    await build({ contentDir, outputDir, templatesDir });

    const html = await fs.readFile(
      path.join(outputDir, "page.html"),
      "utf-8"
    );
    expect(html).toContain("<title>Layouted</title>");
    expect(html).toContain("LAYOUT:");
    expect(html).toContain("CONTENT:");
    expect(html).toContain("<h1>Hello Layout</h1>");
  });

  test("build still works without templatesDir option using defaults", async () => {
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await fs.mkdir(contentDir, { recursive: true });
    await fs.writeFile(
      path.join(contentDir, "basic.md"),
      `---
title: Basic
---

# Basic Page
`
    );

    await build({ contentDir, outputDir });

    const html = await fs.readFile(
      path.join(outputDir, "basic.html"),
      "utf-8"
    );
    expect(html).toContain("Basic");
    expect(html).toContain("<h1>Basic Page</h1>");
  });
});

describe("dev server", () => {
  let servers: Array<{
    close: () => Promise<void>;
  }> = [];

  afterEach(async () => {
    for (const s of servers) {
      await s.close();
    }
    servers = [];
  });

  function httpGet(url: string): Promise<{ body: string; status: number; headers: http.IncomingHttpHeaders }> {
    return new Promise((resolve, reject) => {
      http.get(url, (res) => {
        let body = "";
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          resolve({ body, status: res.statusCode || 0, headers: res.headers });
        });
      }).on("error", reject);
    });
  }

  function getPort(): number {
    return 4000 + Math.floor(Math.random() * 1000);
  }

  test("injectLiveReloadScript injects script before closing body tag", () => {
    const html =
      "<html><head></head><body><p>Hello</p></body></html>";
    const result = injectLiveReloadScript(html, 3000);

    expect(result).toContain("ws://localhost:3000/__livereload");
    expect(result).toContain("WebSocket");
    expect(result).toContain("window.location.reload");
    expect(result).toContain("<p>Hello</p>");

    const bodyCloseIdx = result.lastIndexOf("</body>");
    const scriptIdx = result.indexOf("WebSocket");
    expect(scriptIdx).toBeLessThan(bodyCloseIdx);
  });

  test("dev server serves HTML pages with live reload script", async () => {
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await fs.mkdir(contentDir, { recursive: true });
    await fs.writeFile(
      path.join(contentDir, "test.md"),
      `---
title: Dev Test
---

# Dev Header
`
    );

    const port = getPort();
    const dev = await startDevServer({
      contentDir,
      outputDir,
      port,
    });

    servers.push(dev);

    const { body, status } = await httpGet(
      `http://localhost:${port}/test.html`
    );

    expect(status).toBe(200);
    expect(body).toContain("<title>Dev Test</title>");
    expect(body).toContain("<h1>Dev Header</h1>");
    expect(body).toContain("ws://localhost:" + port + "/__livereload");
    expect(body).toContain("window.location.reload");
  });

  test("dev server serves index.html at root path with live reload script", async () => {
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await fs.mkdir(contentDir, { recursive: true });
    await fs.writeFile(
      path.join(contentDir, "home.md"),
      `---
title: Home Page
---

# Welcome
`
    );

    const port = getPort();
    const dev = await startDevServer({
      contentDir,
      outputDir,
      port,
    });

    servers.push(dev);

    const { body, status } = await httpGet(
      `http://localhost:${port}/`
    );

    expect(status).toBe(200);
    expect(body).toContain("Home Page");
    expect(body).toContain("window.location.reload");
  });

  test("dev server returns 404 for missing files", async () => {
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await fs.mkdir(contentDir, { recursive: true });
    await fs.writeFile(
      path.join(contentDir, "only.md"),
      `---
title: Only
---

# Only page
`
    );

    const port = getPort();
    const dev = await startDevServer({
      contentDir,
      outputDir,
      port,
    });

    servers.push(dev);

    const { body, status } = await httpGet(
      `http://localhost:${port}/nonexistent.html`
    );

    expect(status).toBe(404);
    expect(body).toBe("Not Found");
  });

  test("dev server does not inject script into non-HTML files", async () => {
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await fs.mkdir(contentDir, { recursive: true });
    await fs.writeFile(
      path.join(contentDir, "page.md"),
      `---
title: Page
---

# Page
`
    );

    const port = getPort();
    const dev = await startDevServer({
      contentDir,
      outputDir,
      port,
    });

    servers.push(dev);

    await fs.writeFile(
      path.join(outputDir, "style.css"),
      "body { color: red; }",
      "utf-8"
    );

    const { body, status, headers } = await httpGet(
      `http://localhost:${port}/style.css`
    );

    expect(status).toBe(200);
    expect(body).toBe("body { color: red; }");
    expect(body).not.toContain("WebSocket");
    expect(headers["content-type"]).toContain("text/css");
  });

  test("dev server serves pages from subdirectories", async () => {
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    const subDir = path.join(contentDir, "blog");
    await fs.mkdir(subDir, { recursive: true });
    await fs.writeFile(
      path.join(subDir, "post.md"),
      `---
title: Blog Post
---

# A Blog Post
`
    );

    const port = getPort();
    const dev = await startDevServer({
      contentDir,
      outputDir,
      port,
    });

    servers.push(dev);

    const { body, status } = await httpGet(
      `http://localhost:${port}/blog/post.html`
    );

    expect(status).toBe(200);
    expect(body).toContain("<title>Blog Post</title>");
    expect(body).toContain("<h1>A Blog Post</h1>");
    expect(body).toContain("window.location.reload");
  });

  test("dev server rebuilds on content file change", async () => {
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await fs.mkdir(contentDir, { recursive: true });
    await fs.writeFile(
      path.join(contentDir, "dynamic.md"),
      `---
title: Original
---

# Original Content
`
    );

    const port = getPort();
    const dev = await startDevServer({
      contentDir,
      outputDir,
      port,
    });

    servers.push(dev);

    let { body } = await httpGet(
      `http://localhost:${port}/dynamic.html`
    );
    expect(body).toContain("<title>Original</title>");
    expect(body).toContain("<h1>Original Content</h1>");

    await fs.writeFile(
      path.join(contentDir, "dynamic.md"),
      `---
title: Updated
---

# Updated Content
`
    );

    await new Promise((resolve) => setTimeout(resolve, 500));

    const { body: body2 } = await httpGet(
      `http://localhost:${port}/dynamic.html`
    );
    expect(body2).toContain("<title>Updated</title>");
    expect(body2).toContain("<h1>Updated Content</h1>");
  });

  test("dev server rebuilds on template file change", async () => {
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");
    const templatesDir = path.join(testDir, "templates");

    await fs.mkdir(contentDir, { recursive: true });
    await fs.mkdir(templatesDir, { recursive: true });

    await fs.writeFile(
      path.join(templatesDir, "default.hbs"),
      `<html><body>TEMPLATE_V1: {{{content}}}</body></html>`
    );
    await fs.writeFile(
      path.join(contentDir, "tmpl.md"),
      `---
title: Template Test
---

# Content
`
    );

    const port = getPort();
    const dev = await startDevServer({
      contentDir,
      outputDir,
      templatesDir,
      port,
    });

    servers.push(dev);

    let { body } = await httpGet(
      `http://localhost:${port}/tmpl.html`
    );
    expect(body).toContain("TEMPLATE_V1");

    await fs.writeFile(
      path.join(templatesDir, "default.hbs"),
      `<html><body>TEMPLATE_V2: {{{content}}}</body></html>`
    );

    await new Promise((resolve) => setTimeout(resolve, 500));

    const { body: body2 } = await httpGet(
      `http://localhost:${port}/tmpl.html`
    );
    expect(body2).toContain("TEMPLATE_V2");
  });

  test("dev server uses custom port option", async () => {
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await fs.mkdir(contentDir, { recursive: true });
    await fs.writeFile(
      path.join(contentDir, "porttest.md"),
      `---
title: Port Test
---

# Port
`
    );

    const customPort = getPort();
    const dev = await startDevServer({
      contentDir,
      outputDir,
      port: customPort,
    });

    servers.push(dev);

    const { body, status } = await httpGet(
      `http://localhost:${customPort}/porttest.html`
    );

    expect(status).toBe(200);
    expect(body).toContain("Port Test");
    expect(body).toContain("ws://localhost:" + customPort + "/__livereload");
  });

  test("dev server injects live reload script into index.html", async () => {
    const contentDir = path.join(testDir, "content");
    const outputDir = path.join(testDir, "output");

    await fs.mkdir(contentDir, { recursive: true });
    await fs.writeFile(
      path.join(contentDir, "idx.md"),
      `---
title: Indexed
---

# Indexed
`
    );

    const port = getPort();
    const dev = await startDevServer({
      contentDir,
      outputDir,
      port,
    });

    servers.push(dev);

    const { body, status } = await httpGet(
      `http://localhost:${port}/index.html`
    );

    expect(status).toBe(200);
    expect(body).toContain("window.location.reload");
  });
});
