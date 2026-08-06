import { describe, it, expect, afterEach } from "vitest";
import { createTemplateEngine } from "../src/templates.js";
import { renderMarkdown } from "../src/markdown.js";
import { makeFixture, type Fixture, DEFAULT_LAYOUT, NAV_PARTIAL } from "./helpers.js";

let fixture: Fixture | null = null;
afterEach(async () => {
  await fixture?.cleanup();
  fixture = null;
});

describe("template engine", () => {
  it("renders a layout with context and partials", async () => {
    fixture = await makeFixture({
      "templates/layouts/default.hbs": DEFAULT_LAYOUT,
      "templates/partials/nav.hbs": NAV_PARTIAL,
    });
    const engine = await createTemplateEngine(fixture.templateDir);
    const html = engine.render("default", {
      title: "Post",
      site: { title: "Site" },
      content: "<p>hi</p>",
    });
    expect(html).toContain("<title>Post - Site</title>");
    expect(html).toContain("<nav>home</nav>");
    expect(html).toContain("<main><p>hi</p></main>");
  });

  it("supports nested partials directories", async () => {
    fixture = await makeFixture({
      "templates/layouts/default.hbs": "{{> widgets/badge}}",
      "templates/partials/widgets/badge.hbs": "<span>badge</span>",
    });
    const engine = await createTemplateEngine(fixture.templateDir);
    expect(engine.render("default", {})).toBe("<span>badge</span>");
  });

  it("falls back to root-level templates as layouts", async () => {
    fixture = await makeFixture({ "templates/post.hbs": "root:{{title}}" });
    const engine = await createTemplateEngine(fixture.templateDir);
    expect(engine.hasLayout("post")).toBe(true);
    expect(engine.render("post", { title: "T" })).toBe("root:T");
  });

  it("throws a clear error for a missing layout", async () => {
    fixture = await makeFixture({ "templates/layouts/default.hbs": "x" });
    const engine = await createTemplateEngine(fixture.templateDir);
    expect(() => engine.render("nope", {})).toThrow(/Layout "nope" not found/);
  });

  it("formatDate helper renders dates", async () => {
    fixture = await makeFixture({
      "templates/layouts/default.hbs": "{{formatDate date}}|{{formatDate missing}}",
    });
    const engine = await createTemplateEngine(fixture.templateDir);
    const html = engine.render("default", { date: new Date("2024-05-06T00:00:00Z") });
    expect(html).toBe("2024-05-06|");
  });
});

describe("markdown rendering", () => {
  it("renders markdown to HTML", () => {
    const html = renderMarkdown("# Title\n\nSome *emphasis*.");
    expect(html).toContain("<h1");
    expect(html).toContain("<em>emphasis</em>");
  });

  it("applies syntax highlighting to fenced code blocks", () => {
    const html = renderMarkdown("```js\nconst x = 1;\n```");
    expect(html).toContain('class="hljs language-js"');
    expect(html).toContain("hljs-keyword");
  });

  it("highlights unlabeled code blocks via auto-detection", () => {
    const html = renderMarkdown("```\nfunction f() { return 1; }\n```");
    expect(html).toContain("<code");
    expect(html).toMatch(/hljs-/);
  });
});
