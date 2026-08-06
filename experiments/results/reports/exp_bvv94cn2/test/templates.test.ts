import { describe, it, expect } from "vitest";
import { createTestEngine } from "../src/templates.js";

describe("TemplateEngine", () => {
  const engine = createTestEngine(
    { header: "<nav>Nav</nav>", footer: "<footer>Foot</footer>" },
    "<html><body>{{{body}}}</body></html>"
  );

  it("renders a simple template with data", () => {
    const result = engine.render("<h1>{{title}}</h1>", { title: "Hello" });
    expect(result).toBe("<h1>Hello</h1>");
  });

  it("renders a template with partials", () => {
    const result = engine.render(
      "<div>{{> header}}<p>Body</p>{{> footer}}</div>",
      {}
    );
    expect(result).toContain("<nav>Nav</nav>");
    expect(result).toContain("<footer>Foot</footer>");
    expect(result).toContain("<p>Body</p>");
  });

  it("renderPage wraps content in layout", () => {
    const result = engine.renderPage(
      "<h1>{{title}}</h1>",
      { title: "My Page" }
    );
    expect(result).toContain("<html>");
    expect(result).toContain("<h1>My Page</h1>");
    expect(result).toContain("</body></html>");
  });

  it("renderPage uses provided layout override", () => {
    const result = engine.renderPage(
      "content",
      {},
      "<div>{{{body}}}</div>"
    );
    expect(result).toBe("<div>content</div>");
  });

  it("renderPage without layout returns body only", () => {
    const e = createTestEngine();
    const result = e.renderPage("<p>Raw</p>", {});
    expect(result).toBe("<p>Raw</p>");
  });

  it("handles HTML in data without escaping", () => {
    const result = engine.render("<div>{{{content}}}</div>", {
      content: "<strong>Bold</strong>",
    });
    expect(result).toBe("<div><strong>Bold</strong></div>");
  });

  it("supports each/if helpers", () => {
    const result = engine.render(
      "{{#each items}}<li>{{this}}</li>{{/each}}",
      { items: ["a", "b"] }
    );
    expect(result).toBe("<li>a</li><li>b</li>");
  });

  it("supports nested object access", () => {
    const result = engine.render("<p>{{page.frontmatter.title}}</p>", {
      page: { frontmatter: { title: "Nested" } },
    });
    expect(result).toBe("<p>Nested</p>");
  });
});
