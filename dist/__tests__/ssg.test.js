"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const path_1 = __importDefault(require("path"));
const fs_1 = require("fs");
const os_1 = __importDefault(require("os"));
const http_1 = __importDefault(require("http"));
const index_1 = require("../index");
const dev_server_1 = require("../dev-server");
let testDir;
beforeEach(async () => {
    testDir = await fs_1.promises.mkdtemp(path_1.default.join(os_1.default.tmpdir(), "ssg-test-"));
});
describe("ssg build", () => {
    test("creates output directory", async () => {
        const contentDir = path_1.default.resolve(__dirname, "..", "..", "content");
        const tmpOut = path_1.default.join(testDir, "out1");
        await (0, index_1.build)({ contentDir, outputDir: tmpOut });
        const content = await fs_1.promises.readdir(tmpOut);
        expect(content.length).toBeGreaterThan(0);
    });
    test("generates index.html listing all pages", async () => {
        const contentDir = path_1.default.resolve(__dirname, "..", "..", "content");
        const tmpOut = path_1.default.join(testDir, "out2");
        await (0, index_1.build)({ contentDir, outputDir: tmpOut });
        const indexHtml = await fs_1.promises.readFile(path_1.default.join(tmpOut, "index.html"), "utf-8");
        expect(indexHtml).toContain("<title>Site Index</title>");
        expect(indexHtml).toContain("Hello World");
        expect(indexHtml).toContain("About");
        expect(indexHtml).toContain("No Date Page");
    });
    test("index.html lists pages in alphabetical order by path", async () => {
        const contentDir = path_1.default.resolve(__dirname, "..", "..", "content");
        const tmpOut = path_1.default.join(testDir, "out3");
        await (0, index_1.build)({ contentDir, outputDir: tmpOut });
        const indexHtml = await fs_1.promises.readFile(path_1.default.join(tmpOut, "index.html"), "utf-8");
        const aboutIdx = indexHtml.indexOf("About");
        const helloIdx = indexHtml.indexOf("Hello World");
        const notagsIdx = indexHtml.indexOf("No Date Page");
        expect(aboutIdx).toBeLessThan(helloIdx);
        expect(helloIdx).toBeLessThan(notagsIdx);
    });
    test("generates individual HTML pages", async () => {
        const contentDir = path_1.default.resolve(__dirname, "..", "..", "content");
        const tmpOut = path_1.default.join(testDir, "out4");
        await (0, index_1.build)({ contentDir, outputDir: tmpOut });
        const aboutHtml = await fs_1.promises.readFile(path_1.default.join(tmpOut, "about.html"), "utf-8");
        expect(aboutHtml).toContain("<title>About</title>");
        expect(aboutHtml).toContain("<h2>About This Site</h2>");
        const helloHtml = await fs_1.promises.readFile(path_1.default.join(tmpOut, "hello.html"), "utf-8");
        expect(helloHtml).toContain("<title>Hello World</title>");
        expect(helloHtml).toContain("<h1>Hello World</h1>");
    });
    test("index.html uses frontmatter as unescaped HTML strings", async () => {
        const contentDir = path_1.default.resolve(__dirname, "..", "..", "content");
        const tmpOut = path_1.default.join(testDir, "out5");
        await (0, index_1.build)({ contentDir, outputDir: tmpOut });
        const indexHtml = await fs_1.promises.readFile(path_1.default.join(tmpOut, "index.html"), "utf-8");
        expect(indexHtml).toContain("2024-01-15");
        expect(indexHtml).toContain("Tags: intro, hello");
        expect(indexHtml).toContain("2024-02-20");
        expect(indexHtml).toContain("Tags: meta");
    });
    test("pages with no date/tags omit those sections", async () => {
        const contentDir = path_1.default.resolve(__dirname, "..", "..", "content");
        const tmpOut = path_1.default.join(testDir, "out6");
        await (0, index_1.build)({ contentDir, outputDir: tmpOut });
        const notagsHtml = await fs_1.promises.readFile(path_1.default.join(tmpOut, "notags.html"), "utf-8");
        expect(notagsHtml).not.toContain("class=\"date\"");
        expect(notagsHtml).not.toContain("class=\"tags\"");
    });
    test("markdown body is rendered as HTML in page output", async () => {
        const contentDir = path_1.default.resolve(__dirname, "..", "..", "content");
        const tmpOut = path_1.default.join(testDir, "out7");
        await (0, index_1.build)({ contentDir, outputDir: tmpOut });
        const aboutHtml = await fs_1.promises.readFile(path_1.default.join(tmpOut, "about.html"), "utf-8");
        expect(aboutHtml).toContain("<li>Item one</li>");
        expect(aboutHtml).toContain("<li>Item two</li>");
    });
    test("error on missing content directory", async () => {
        const badDir = path_1.default.join(testDir, "nonexistent");
        const tmpOut = path_1.default.join(testDir, "out8");
        await expect((0, index_1.build)({ contentDir: badDir, outputDir: tmpOut })).rejects.toThrow("Content directory not found");
    });
    test("creates subdirectory output for files in subdirectories", async () => {
        const contentDir = path_1.default.join(testDir, "content-nested");
        const subDir = path_1.default.join(contentDir, "posts");
        await fs_1.promises.mkdir(subDir, { recursive: true });
        await fs_1.promises.writeFile(path_1.default.join(subDir, "nested-post.md"), `---
title: Nested Post
---

# Nested

Content in a subdirectory.
`);
        await fs_1.promises.writeFile(path_1.default.join(contentDir, "root-page.md"), `---
title: Root Page
---

# Root

Content at root level.
`);
        const tmpOut = path_1.default.join(testDir, "out9");
        await (0, index_1.build)({ contentDir, outputDir: tmpOut });
        const nestedExists = await fs_1.promises
            .access(path_1.default.join(tmpOut, "posts", "nested-post.html"))
            .then(() => true)
            .catch(() => false);
        expect(nestedExists).toBe(true);
        const rootExists = await fs_1.promises
            .access(path_1.default.join(tmpOut, "root-page.html"))
            .then(() => true)
            .catch(() => false);
        expect(rootExists).toBe(true);
        const nestedHtml = await fs_1.promises.readFile(path_1.default.join(tmpOut, "posts", "nested-post.html"), "utf-8");
        expect(nestedHtml).toContain("<title>Nested Post</title>");
        const indexHtml = await fs_1.promises.readFile(path_1.default.join(tmpOut, "index.html"), "utf-8");
        expect(indexHtml).toContain("Nested Post");
        expect(indexHtml).toContain("Root Page");
        expect(indexHtml).toContain('href="posts/nested-post.html"');
        expect(indexHtml).toContain('href="root-page.html"');
    });
});
describe("template engine", () => {
    async function setupTemplateContent(templatesDir, contentDir, templateFiles, contentFiles) {
        for (const [relPath, content] of Object.entries(templateFiles)) {
            const fullPath = path_1.default.join(templatesDir, relPath);
            await fs_1.promises.mkdir(path_1.default.dirname(fullPath), { recursive: true });
            await fs_1.promises.writeFile(fullPath, content, "utf-8");
        }
        for (const [relPath, content] of Object.entries(contentFiles)) {
            const fullPath = path_1.default.join(contentDir, relPath);
            await fs_1.promises.mkdir(path_1.default.dirname(fullPath), { recursive: true });
            await fs_1.promises.writeFile(fullPath, content, "utf-8");
        }
    }
    test("uses default template when no template specified in frontmatter", async () => {
        const templatesDir = path_1.default.join(testDir, "templates");
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await setupTemplateContent(templatesDir, contentDir, {
            "default.hbs": `<!DOCTYPE html><html><head><title>{{title}}</title></head><body>{{{content}}}</body></html>`,
        }, {
            "page.md": `---
title: My Page
---

# Hello

World
`,
        });
        await (0, index_1.build)({ contentDir, outputDir, templatesDir });
        const html = await fs_1.promises.readFile(path_1.default.join(outputDir, "page.html"), "utf-8");
        expect(html).toContain("<title>My Page</title>");
        expect(html).toContain("<h1>Hello</h1>");
        expect(html).toContain("<p>World</p>");
    });
    test("uses custom template from frontmatter template field", async () => {
        const templatesDir = path_1.default.join(testDir, "templates");
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await setupTemplateContent(templatesDir, contentDir, {
            "default.hbs": `<html><body>DEFAULT</body></html>`,
            "custom.hbs": `<html><body>CUSTOM: {{title}} {{{content}}}</body></html>`,
        }, {
            "page.md": `---
title: Special
template: custom
---

# Custom Page
`,
        });
        await (0, index_1.build)({ contentDir, outputDir, templatesDir });
        const html = await fs_1.promises.readFile(path_1.default.join(outputDir, "page.html"), "utf-8");
        expect(html).toContain("CUSTOM: Special");
        expect(html).toContain("<h1>Custom Page</h1>");
        expect(html).not.toContain("DEFAULT");
    });
    test("layout template wraps page content with body placeholder", async () => {
        const templatesDir = path_1.default.join(testDir, "templates");
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await setupTemplateContent(templatesDir, contentDir, {
            "default.hbs": `<main><h1>{{title}}</h1>{{{content}}}</main>`,
            "layouts/wrapper.hbs": `<html><head><title>{{title}}</title></head><body>WRAPPER_START{{{body}}}WRAPPER_END</body></html>`,
        }, {
            "page.md": `---
title: Layout Page
layout: wrapper
---

# Content
`,
        });
        await (0, index_1.build)({ contentDir, outputDir, templatesDir });
        const html = await fs_1.promises.readFile(path_1.default.join(outputDir, "page.html"), "utf-8");
        expect(html).toContain("WRAPPER_START");
        expect(html).toContain("WRAPPER_END");
        expect(html).toContain("<h1>Layout Page</h1>");
        expect(html).toContain("<h1>Content</h1>");
    });
    test("partials are included in templates", async () => {
        const templatesDir = path_1.default.join(testDir, "templates");
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await setupTemplateContent(templatesDir, contentDir, {
            "default.hbs": `<html><body>{{> header}}{{{content}}}{{> footer}}</body></html>`,
            "partials/header.hbs": `<header>SITE HEADER</header>`,
            "partials/footer.hbs": `<footer>SITE FOOTER</footer>`,
        }, {
            "page.md": `---
title: Partial Test
---

# Page
`,
        });
        await (0, index_1.build)({ contentDir, outputDir, templatesDir });
        const html = await fs_1.promises.readFile(path_1.default.join(outputDir, "page.html"), "utf-8");
        expect(html).toContain("<header>SITE HEADER</header>");
        expect(html).toContain("<footer>SITE FOOTER</footer>");
        expect(html).toContain("<h1>Page</h1>");
    });
    test("nav partial is available in layouts", async () => {
        const templatesDir = path_1.default.join(testDir, "templates");
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await setupTemplateContent(templatesDir, contentDir, {
            "default.hbs": `<main>{{{content}}}</main>`,
            "layouts/nav-layout.hbs": `<html><body>{{> nav}}{{{body}}}</body></html>`,
            "partials/nav.hbs": `<nav><a href="/">Home</a></nav>`,
        }, {
            "page.md": `---
title: Nav Test
layout: nav-layout
---

# Nav Page
`,
        });
        await (0, index_1.build)({ contentDir, outputDir, templatesDir });
        const html = await fs_1.promises.readFile(path_1.default.join(outputDir, "page.html"), "utf-8");
        expect(html).toContain('<nav><a href="/">Home</a></nav>');
        expect(html).toContain("<h1>Nav Page</h1>");
    });
    test("falls back to inline generation when template directory does not exist", async () => {
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        const templatesDir = path_1.default.join(testDir, "nonexistent-templates");
        await fs_1.promises.mkdir(contentDir, { recursive: true });
        await fs_1.promises.writeFile(path_1.default.join(contentDir, "page.md"), `---
title: Inline Page
---

# Inline Content
`);
        await (0, index_1.build)({ contentDir, outputDir, templatesDir });
        const html = await fs_1.promises.readFile(path_1.default.join(outputDir, "page.html"), "utf-8");
        expect(html).toContain("<title>Inline Page</title>");
        expect(html).toContain("<h1>Inline Content</h1>");
        expect(html).toContain("<!DOCTYPE html>");
    });
    test("uses index template when index.hbs exists", async () => {
        const templatesDir = path_1.default.join(testDir, "templates");
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await setupTemplateContent(templatesDir, contentDir, {
            "default.hbs": `<html><body>{{{content}}}</body></html>`,
            "index.hbs": `<html><body>TEMPLATED INDEX<ul>{{#each pages}}<li>{{title}}</li>{{/each}}</ul></body></html>`,
        }, {
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
        });
        await (0, index_1.build)({ contentDir, outputDir, templatesDir });
        const indexHtml = await fs_1.promises.readFile(path_1.default.join(outputDir, "index.html"), "utf-8");
        expect(indexHtml).toContain("TEMPLATED INDEX");
        expect(indexHtml).toContain("<li>First</li>");
        expect(indexHtml).toContain("<li>Second</li>");
    });
    test("template engine handles pages with layout specified in frontmatter", async () => {
        const templatesDir = path_1.default.join(testDir, "templates");
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await setupTemplateContent(templatesDir, contentDir, {
            "default.hbs": `<div>CONTENT: {{{content}}}</div>`,
            "layouts/base.hbs": `<html><head><title>{{title}}</title></head><body>LAYOUT:{{{body}}}</body></html>`,
        }, {
            "page.md": `---
title: Layouted
layout: base
---

# Hello Layout
`,
        });
        await (0, index_1.build)({ contentDir, outputDir, templatesDir });
        const html = await fs_1.promises.readFile(path_1.default.join(outputDir, "page.html"), "utf-8");
        expect(html).toContain("<title>Layouted</title>");
        expect(html).toContain("LAYOUT:");
        expect(html).toContain("CONTENT:");
        expect(html).toContain("<h1>Hello Layout</h1>");
    });
    test("build still works without templatesDir option using defaults", async () => {
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await fs_1.promises.mkdir(contentDir, { recursive: true });
        await fs_1.promises.writeFile(path_1.default.join(contentDir, "basic.md"), `---
title: Basic
---

# Basic Page
`);
        await (0, index_1.build)({ contentDir, outputDir });
        const html = await fs_1.promises.readFile(path_1.default.join(outputDir, "basic.html"), "utf-8");
        expect(html).toContain("Basic");
        expect(html).toContain("<h1>Basic Page</h1>");
    });
});
describe("dev server", () => {
    let servers = [];
    afterEach(async () => {
        for (const s of servers) {
            await s.close();
        }
        servers = [];
    });
    function httpGet(url) {
        return new Promise((resolve, reject) => {
            http_1.default.get(url, (res) => {
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
    function getPort() {
        return 4000 + Math.floor(Math.random() * 1000);
    }
    test("injectLiveReloadScript injects script before closing body tag", () => {
        const html = "<html><head></head><body><p>Hello</p></body></html>";
        const result = (0, dev_server_1.injectLiveReloadScript)(html, 3000);
        expect(result).toContain("ws://localhost:3000/__livereload");
        expect(result).toContain("WebSocket");
        expect(result).toContain("window.location.reload");
        expect(result).toContain("<p>Hello</p>");
        const bodyCloseIdx = result.lastIndexOf("</body>");
        const scriptIdx = result.indexOf("WebSocket");
        expect(scriptIdx).toBeLessThan(bodyCloseIdx);
    });
    test("dev server serves HTML pages with live reload script", async () => {
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await fs_1.promises.mkdir(contentDir, { recursive: true });
        await fs_1.promises.writeFile(path_1.default.join(contentDir, "test.md"), `---
title: Dev Test
---

# Dev Header
`);
        const port = getPort();
        const dev = await (0, dev_server_1.startDevServer)({
            contentDir,
            outputDir,
            port,
        });
        servers.push(dev);
        const { body, status } = await httpGet(`http://localhost:${port}/test.html`);
        expect(status).toBe(200);
        expect(body).toContain("<title>Dev Test</title>");
        expect(body).toContain("<h1>Dev Header</h1>");
        expect(body).toContain("ws://localhost:" + port + "/__livereload");
        expect(body).toContain("window.location.reload");
    });
    test("dev server serves index.html at root path with live reload script", async () => {
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await fs_1.promises.mkdir(contentDir, { recursive: true });
        await fs_1.promises.writeFile(path_1.default.join(contentDir, "home.md"), `---
title: Home Page
---

# Welcome
`);
        const port = getPort();
        const dev = await (0, dev_server_1.startDevServer)({
            contentDir,
            outputDir,
            port,
        });
        servers.push(dev);
        const { body, status } = await httpGet(`http://localhost:${port}/`);
        expect(status).toBe(200);
        expect(body).toContain("Home Page");
        expect(body).toContain("window.location.reload");
    });
    test("dev server returns 404 for missing files", async () => {
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await fs_1.promises.mkdir(contentDir, { recursive: true });
        await fs_1.promises.writeFile(path_1.default.join(contentDir, "only.md"), `---
title: Only
---

# Only page
`);
        const port = getPort();
        const dev = await (0, dev_server_1.startDevServer)({
            contentDir,
            outputDir,
            port,
        });
        servers.push(dev);
        const { body, status } = await httpGet(`http://localhost:${port}/nonexistent.html`);
        expect(status).toBe(404);
        expect(body).toBe("Not Found");
    });
    test("dev server does not inject script into non-HTML files", async () => {
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await fs_1.promises.mkdir(contentDir, { recursive: true });
        await fs_1.promises.writeFile(path_1.default.join(contentDir, "page.md"), `---
title: Page
---

# Page
`);
        const port = getPort();
        const dev = await (0, dev_server_1.startDevServer)({
            contentDir,
            outputDir,
            port,
        });
        servers.push(dev);
        await fs_1.promises.writeFile(path_1.default.join(outputDir, "style.css"), "body { color: red; }", "utf-8");
        const { body, status, headers } = await httpGet(`http://localhost:${port}/style.css`);
        expect(status).toBe(200);
        expect(body).toBe("body { color: red; }");
        expect(body).not.toContain("WebSocket");
        expect(headers["content-type"]).toContain("text/css");
    });
    test("dev server serves pages from subdirectories", async () => {
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        const subDir = path_1.default.join(contentDir, "blog");
        await fs_1.promises.mkdir(subDir, { recursive: true });
        await fs_1.promises.writeFile(path_1.default.join(subDir, "post.md"), `---
title: Blog Post
---

# A Blog Post
`);
        const port = getPort();
        const dev = await (0, dev_server_1.startDevServer)({
            contentDir,
            outputDir,
            port,
        });
        servers.push(dev);
        const { body, status } = await httpGet(`http://localhost:${port}/blog/post.html`);
        expect(status).toBe(200);
        expect(body).toContain("<title>Blog Post</title>");
        expect(body).toContain("<h1>A Blog Post</h1>");
        expect(body).toContain("window.location.reload");
    });
    test("dev server rebuilds on content file change", async () => {
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await fs_1.promises.mkdir(contentDir, { recursive: true });
        await fs_1.promises.writeFile(path_1.default.join(contentDir, "dynamic.md"), `---
title: Original
---

# Original Content
`);
        const port = getPort();
        const dev = await (0, dev_server_1.startDevServer)({
            contentDir,
            outputDir,
            port,
        });
        servers.push(dev);
        let { body } = await httpGet(`http://localhost:${port}/dynamic.html`);
        expect(body).toContain("<title>Original</title>");
        expect(body).toContain("<h1>Original Content</h1>");
        await fs_1.promises.writeFile(path_1.default.join(contentDir, "dynamic.md"), `---
title: Updated
---

# Updated Content
`);
        await new Promise((resolve) => setTimeout(resolve, 500));
        const { body: body2 } = await httpGet(`http://localhost:${port}/dynamic.html`);
        expect(body2).toContain("<title>Updated</title>");
        expect(body2).toContain("<h1>Updated Content</h1>");
    });
    test("dev server rebuilds on template file change", async () => {
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        const templatesDir = path_1.default.join(testDir, "templates");
        await fs_1.promises.mkdir(contentDir, { recursive: true });
        await fs_1.promises.mkdir(templatesDir, { recursive: true });
        await fs_1.promises.writeFile(path_1.default.join(templatesDir, "default.hbs"), `<html><body>TEMPLATE_V1: {{{content}}}</body></html>`);
        await fs_1.promises.writeFile(path_1.default.join(contentDir, "tmpl.md"), `---
title: Template Test
---

# Content
`);
        const port = getPort();
        const dev = await (0, dev_server_1.startDevServer)({
            contentDir,
            outputDir,
            templatesDir,
            port,
        });
        servers.push(dev);
        let { body } = await httpGet(`http://localhost:${port}/tmpl.html`);
        expect(body).toContain("TEMPLATE_V1");
        await fs_1.promises.writeFile(path_1.default.join(templatesDir, "default.hbs"), `<html><body>TEMPLATE_V2: {{{content}}}</body></html>`);
        await new Promise((resolve) => setTimeout(resolve, 500));
        const { body: body2 } = await httpGet(`http://localhost:${port}/tmpl.html`);
        expect(body2).toContain("TEMPLATE_V2");
    });
    test("dev server uses custom port option", async () => {
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await fs_1.promises.mkdir(contentDir, { recursive: true });
        await fs_1.promises.writeFile(path_1.default.join(contentDir, "porttest.md"), `---
title: Port Test
---

# Port
`);
        const customPort = getPort();
        const dev = await (0, dev_server_1.startDevServer)({
            contentDir,
            outputDir,
            port: customPort,
        });
        servers.push(dev);
        const { body, status } = await httpGet(`http://localhost:${customPort}/porttest.html`);
        expect(status).toBe(200);
        expect(body).toContain("Port Test");
        expect(body).toContain("ws://localhost:" + customPort + "/__livereload");
    });
    test("dev server injects live reload script into index.html", async () => {
        const contentDir = path_1.default.join(testDir, "content");
        const outputDir = path_1.default.join(testDir, "output");
        await fs_1.promises.mkdir(contentDir, { recursive: true });
        await fs_1.promises.writeFile(path_1.default.join(contentDir, "idx.md"), `---
title: Indexed
---

# Indexed
`);
        const port = getPort();
        const dev = await (0, dev_server_1.startDevServer)({
            contentDir,
            outputDir,
            port,
        });
        servers.push(dev);
        const { body, status } = await httpGet(`http://localhost:${port}/index.html`);
        expect(status).toBe(200);
        expect(body).toContain("window.location.reload");
    });
});
