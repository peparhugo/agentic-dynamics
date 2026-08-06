import { describe, it, expect, beforeAll, afterAll } from "vitest";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import { TemplateEngine } from "../src/render";

describe("TemplateEngine", () => {
  let tmpDir: string;

  beforeAll(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ssg-test-"));
  });

  afterAll(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  function setupTemplates(files: Record<string, string>) {
    for (const [name, content] of Object.entries(files)) {
      const filePath = path.join(tmpDir, name);
      fs.mkdirSync(path.dirname(filePath), { recursive: true });
      fs.writeFileSync(filePath, content);
    }
  }

  it("renders a simple template", () => {
    setupTemplates({
      "post.hbs": "<h1>{{title}}</h1>\n<p>{{body}}</p>",
    });

    const engine = new TemplateEngine(tmpDir);
    const result = engine.render("post", { title: "Hello", body: "<p>World</p>" });

    expect(result).toContain("<h1>Hello</h1>");
    expect(result).toContain("<p>World</p>");
  });

  it("renders with layout template", () => {
    setupTemplates({
      "layout.hbs": "<html><head><title>{{title}}</title></head><body>{{{body}}}</body></html>",
      "post.hbs": "<h1>{{title}}</h1>",
    });

    const engine = new TemplateEngine(tmpDir);
    const result = engine.render("post", { title: "My Post" });

    expect(result).toContain("<html>");
    expect(result).toContain("<h1>My Post</h1>");
    expect(result).toContain("</html>");
  });

  it("renders with partials", () => {
    setupTemplates({
      "post.hbs": "<header>{{> header}}</header><main>{{{body}}}</main>",
      "partials/header.hbs": "<h1>{{title}}</h1><nav>Menu</nav>",
    });

    const engine = new TemplateEngine(tmpDir);
    const result = engine.render("post", { title: "Post", body: "Content" });

    expect(result).toContain("<h1>Post</h1>");
    expect(result).toContain("<nav>Menu</nav>");
    expect(result).toContain("Content");
  });

  it("uses formatDate helper correctly", () => {
    setupTemplates({
      "post.hbs": "<time>{{formatDate date}}</time>",
    });

    const engine = new TemplateEngine(tmpDir);
    const result = engine.render("post", { date: new Date("2024-03-15") });

    expect(result).toContain("2024-03-15");
  });

  it("returns empty string for missing template", () => {
    setupTemplates({});
    const engine = new TemplateEngine(tmpDir);
    const result = engine.render("nonexistent", {});
    expect(result).toBe("");
  });

  it("hasTemplate returns correct boolean", () => {
    setupTemplates({ "post.hbs": "hello" });
    const engine = new TemplateEngine(tmpDir);
    expect(engine.hasTemplate("post")).toBe(true);
    expect(engine.hasTemplate("missing")).toBe(false);
  });

  it("handles .handlebars extension", () => {
    setupTemplates({ "post.handlebars": "<h1>{{title}}</h1>" });
    const engine = new TemplateEngine(tmpDir);
    expect(engine.hasTemplate("post")).toBe(true);
    const result = engine.render("post", { title: "Alt" });
    expect(result).toContain("<h1>Alt</h1>");
  });

  it("escapes HTML by default", () => {
    setupTemplates({ "post.hbs": "<p>{{body}}</p>" });
    const engine = new TemplateEngine(tmpDir);
    const result = engine.render("post", { body: "<script>alert('xss')</script>" });

    expect(result).not.toContain("<script>");
    expect(result).toContain("&lt;script&gt;");
  });

  it("renders raw HTML with triple braces", () => {
    setupTemplates({ "post.hbs": "<p>{{{body}}}</p>" });
    const engine = new TemplateEngine(tmpDir);
    const result = engine.render("post", { body: "<em>safe</em>" });

    expect(result).toContain("<em>safe</em>");
  });
});
