import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import { TemplateEngine } from "../src/templates";

describe("TemplateEngine", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "triton-templates-"));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  function writeTemplate(name: string, content: string): void {
    const fullPath = path.join(tmpDir, name);
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, content);
  }

  it("loads and renders a template", () => {
    writeTemplate("page.hbs", "<h1>{{page.title}}</h1><div>{{{content}}}</div>");

    const engine = new TemplateEngine(tmpDir);
    engine.load();

    const html = engine.render("page", {
      page: { title: "Hello" },
      content: "<p>World</p>",
    });

    expect(html).toContain("<h1>Hello</h1>");
    expect(html).toContain("<p>World</p>");
  });

  it("wraps content with a layout template", () => {
    writeTemplate("default.hbs", '<html><body><main>{{{content}}}</main></body></html>');
    writeTemplate("page.hbs", '<article>{{{content}}}</article>');

    const engine = new TemplateEngine(tmpDir);
    engine.load();

    const html = engine.render("page", {
      page: { title: "Test" },
      content: "<p>Body</p>",
    });

    expect(html).toContain("<html>");
    expect(html).toContain("<article>");
    expect(html).toContain("<p>Body</p>");
    expect(html).toContain("</html>");
  });

  it("respects custom layout from page frontmatter", () => {
    writeTemplate("default.hbs", '<html>{{{content}}}</html>');
    writeTemplate("custom.hbs", '<div class="custom">{{{content}}}</div>');
    writeTemplate("page.hbs", '<p>{{{content}}}</p>');

    const engine = new TemplateEngine(tmpDir);
    engine.load();

    const html = engine.render("page", {
      page: { title: "Test", layout: "custom" },
      content: "Hello",
    });

    expect(html).toContain('<div class="custom">');
    expect(html).not.toContain("<html>");
  });

  it("loads and uses partials", () => {
    writeTemplate("partials/header.hbs", "<header>{{site.title}}</header>");
    writeTemplate("default.hbs", "<html>{{> header}}{{{content}}}</html>");
    writeTemplate("page.hbs", "{{{content}}}");

    const engine = new TemplateEngine(tmpDir);
    engine.load();

    const html = engine.render("page", {
      page: { title: "Test" },
      site: { title: "My Site" },
      content: "<p>Hi</p>",
    });

    expect(html).toContain("<header>My Site</header>");
  });

  it("throws for missing template", () => {
    const engine = new TemplateEngine(tmpDir);
    engine.load();

    expect(() => engine.render("nonexistent", {})).toThrow("Template not found");
  });

  it("handles empty template directory gracefully", () => {
    const engine = new TemplateEngine("/nonexistent/path");
    engine.load();
    expect(engine.hasTemplate("anything")).toBe(false);
  });

  it("supports Handlebars each helper", () => {
    writeTemplate("index.hbs", "<ul>{{#each pages}}<li>{{title}}</li>{{/each}}</ul>");

    const engine = new TemplateEngine(tmpDir);
    engine.load();

    const html = engine.render("index", {
      pages: [{ title: "A" }, { title: "B" }],
    });

    expect(html).toContain("<li>A</li>");
    expect(html).toContain("<li>B</li>");
  });

  it("supports nested partial directories", () => {
    writeTemplate("partials/ui/button.hbs", '<button>{{text}}</button>');
    writeTemplate("default.hbs", "{{> ui/button}}{{{content}}}");
    writeTemplate("page.hbs", "x");

    const engine = new TemplateEngine(tmpDir);
    engine.load();

    const html = engine.render("page", {
      page: { title: "T" },
      text: "Click",
      content: "",
    });

    expect(html).toContain("<button>Click</button>");
  });
});
