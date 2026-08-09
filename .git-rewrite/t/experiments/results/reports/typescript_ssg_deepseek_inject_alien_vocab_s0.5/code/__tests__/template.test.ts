import { describe, it, expect, beforeEach } from "vitest";
import Handlebars from "handlebars";
import { registerHelpers, registerPartials, loadTemplate, renderTemplate, renderWithLayout } from "../src/lib/template";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

describe("template rendering", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "statick-test-"));
  });

  function writeFile(subPath: string, content: string): void {
    const fullPath = path.join(tmpDir, subPath);
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, content, "utf-8");
  }

  it("renders a basic template", () => {
    Handlebars.unregisterHelper("formatDate");
    Handlebars.unregisterHelper("isoDate");
    Handlebars.unregisterHelper("rfc822Date");
    Handlebars.unregisterHelper("encodeURI");
    registerHelpers();

    writeFile("page.hbs", "<h1>{{title}}</h1><p>{{body}}</p>");
    writeFile("layouts/default.hbs", "<html><body>{{{content}}}</body></html>");

    const result = renderTemplate(tmpDir, "page", { title: "Hello", body: "World" });
    expect(result).toContain("<h1>Hello</h1>");
    expect(result).toContain("<html>");
    expect(result).toContain("<body>");
  });

  it("supports custom layout", () => {
    Handlebars.unregisterHelper("formatDate");
    Handlebars.unregisterHelper("isoDate");
    Handlebars.unregisterHelper("rfc822Date");
    Handlebars.unregisterHelper("encodeURI");
    registerHelpers();

    writeFile("post.hbs", "<article>{{text}}</article>");
    writeFile("layouts/blog.hbs", '<main class="blog">{{{content}}}</main>');

    const result = renderTemplate(tmpDir, "post", { text: "Hello" }, "blog");
    expect(result).toContain('<main class="blog">');
    expect(result).toContain("<article>Hello</article>");
  });

  it("registers and uses partials", () => {
    Handlebars.unregisterHelper("formatDate");
    Handlebars.unregisterHelper("isoDate");
    Handlebars.unregisterHelper("rfc822Date");
    Handlebars.unregisterHelper("encodeURI");
    registerHelpers();

    writeFile("partials/header.hbs", '<header>{{siteName}}</header>');
    writeFile("index.hbs", "{{> header}}<main>content</main>");
    writeFile("layouts/default.hbs", "<html>{{{content}}}</html>");

    registerPartials(tmpDir);
    const result = renderTemplate(tmpDir, "index", { siteName: "My Site" });
    expect(result).toContain("<header>My Site</header>");
    expect(result).toContain("<main>content</main>");
  });

  it("formatDate helper formats dates correctly", () => {
    Handlebars.unregisterHelper("formatDate");
    Handlebars.unregisterHelper("isoDate");
    Handlebars.unregisterHelper("rfc822Date");
    Handlebars.unregisterHelper("encodeURI");
    registerHelpers();

    const result = Handlebars.compile("{{formatDate date}}")({
      date: "2024-03-15",
    });
    expect(result).toMatch(/March 15, 2024/);
  });

  it("formatDate returns empty string for missing date", () => {
    Handlebars.unregisterHelper("formatDate");
    Handlebars.unregisterHelper("isoDate");
    Handlebars.unregisterHelper("rfc822Date");
    Handlebars.unregisterHelper("encodeURI");
    registerHelpers();

    const result = Handlebars.compile("{{formatDate date}}")({});
    expect(result).toBe("");
  });

  it("formatDate returns raw value for invalid date", () => {
    Handlebars.unregisterHelper("formatDate");
    Handlebars.unregisterHelper("isoDate");
    Handlebars.unregisterHelper("rfc822Date");
    Handlebars.unregisterHelper("encodeURI");
    registerHelpers();

    const result = Handlebars.compile("{{formatDate date}}")({
      date: "not-a-date",
    });
    expect(result).toBe("not-a-date");
  });

  it("rfc822Date helper produces UTC string", () => {
    Handlebars.unregisterHelper("formatDate");
    Handlebars.unregisterHelper("isoDate");
    Handlebars.unregisterHelper("rfc822Date");
    Handlebars.unregisterHelper("encodeURI");
    registerHelpers();

    const result = Handlebars.compile("{{rfc822Date date}}")({
      date: "2024-01-01",
    });
    expect(result).toMatch(/GMT$/);
  });

  it("throws when loading missing template", () => {
    expect(() => loadTemplate(tmpDir, "nonexistent")).toThrow("Template not found");
  });

  it("renders without layout when layout file is missing", () => {
    const result = renderWithLayout(tmpDir, "<p>Hi</p>", {});
    expect(result).toBe("<p>Hi</p>");
  });
});
