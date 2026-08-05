import { describe, it, expect } from "vitest";
import { TemplateEngine } from "../src/templates.js";
import { makeFixture } from "./helpers.js";

describe("TemplateEngine", () => {
  it("renders a layout with page/site context and raw content", () => {
    const engine = TemplateEngine.fromSources({
      layouts: { default: "<h1>{{page.title}}</h1><main>{{{content}}}</main> — {{site.title}}" },
    });
    const html = engine.render("default", {
      content: "<p>Hi</p>",
      page: { title: "Page" },
      site: { title: "Site" },
    });
    expect(html).toBe("<h1>Page</h1><main><p>Hi</p></main> — Site");
  });

  it("renders partials", () => {
    const engine = TemplateEngine.fromSources({
      layouts: { default: "{{> nav}}<div>{{{content}}}</div>" },
      partials: { nav: "<nav>{{site.title}}</nav>" },
    });
    const html = engine.render("default", { content: "x", site: { title: "S" } });
    expect(html).toBe("<nav>S</nav><div>x</div>");
  });

  it("escapes {{content}} but not {{{content}}}", () => {
    const engine = TemplateEngine.fromSources({
      layouts: { esc: "{{content}}", raw: "{{{content}}}" },
    });
    expect(engine.render("esc", { content: "<b>x</b>" })).toBe("&lt;b&gt;x&lt;/b&gt;");
    expect(engine.render("raw", { content: "<b>x</b>" })).toBe("<b>x</b>");
  });

  it("falls back to the default layout, then to a built-in layout", () => {
    const withDefault = TemplateEngine.fromSources({
      layouts: { default: "D:{{{content}}}" },
    });
    expect(withDefault.render("missing", { content: "x" })).toBe("D:x");

    const empty = TemplateEngine.fromSources({});
    const html = empty.render("missing", {
      content: "<p>x</p>",
      page: { title: "T" },
      site: { title: "S" },
    });
    expect(html).toContain("<p>x</p>");
    expect(html).toContain("<title>T — S</title>");
  });

  it("formatDate helper renders ISO and human formats, empty for null", () => {
    const engine = TemplateEngine.fromSources({
      layouts: {
        iso: "{{formatDate page.date}}",
        human: '{{formatDate page.date "human"}}',
      },
    });
    const date = new Date("2026-01-15T00:00:00Z");
    expect(engine.render("iso", { page: { date } })).toBe("2026-01-15");
    expect(engine.render("human", { page: { date } })).toBe("January 15, 2026");
    expect(engine.render("iso", { page: { date: null } })).toBe("");
  });

  it("join helper joins arrays", () => {
    const engine = TemplateEngine.fromSources({
      layouts: { l: '{{join page.tags ", "}}' },
    });
    expect(engine.render("l", { page: { tags: ["a", "b"] } })).toBe("a, b");
  });

  it("loads layouts and partials from a directory", async () => {
    const fixture = await makeFixture();
    try {
      const engine = await TemplateEngine.fromDir(fixture.templateDir);
      expect(engine.hasLayout("default")).toBe(true);
      expect(engine.hasLayout("post")).toBe(true);
      const html = engine.render("default", {
        content: "<p>body</p>",
        page: { title: "P" },
        site: { title: "S" },
      });
      expect(html).toContain('<header class="site-header">S</header>');
      expect(html).toContain("<p>body</p>");
    } finally {
      await fixture.cleanup();
    }
  });
});
