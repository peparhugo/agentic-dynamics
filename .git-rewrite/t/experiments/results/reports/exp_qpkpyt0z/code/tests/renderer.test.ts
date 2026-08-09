import { describe, it, expect, beforeAll } from "vitest";
import { compile, loadTemplate, renderPage, loadPartials } from "../src/renderer.js";
import { makeConfig } from "./helpers.js";
import Handlebars from "handlebars";

describe("compile", () => {
  it("compiles a Handlebars template", () => {
    const tpl = compile("Hello {{name}}");
    expect(tpl({ name: "World" })).toBe("Hello World");
  });

  it("renders with HTML escaping when needed", () => {
    const tpl = compile("Escaped: {{value}}");
    expect(tpl({ value: "<script>" })).toBe("Escaped: &lt;script&gt;");
  });
});

describe("loadPartials", () => {
  it("loads partials from directory", async () => {
    const config = makeConfig();
    await loadPartials(config.templateDir + "/partials");
    const partials = Handlebars.partials;
    expect(partials["header"]).toBeDefined();
    expect(partials["footer"]).toBeDefined();
  });
});

describe("loadTemplate", () => {
  it("loads and caches a template from disk", async () => {
    const config = makeConfig();
    const tpl = await loadTemplate(config, "post");
    const result = tpl({ title: "Test", date: "2024-01-01", content: "<p>Hello</p>" });
    expect(result).toContain("Test");
    expect(result).toContain("2024-01-01");
  });
});

describe("renderPage", () => {
  it("renders a page using a named template", async () => {
    const config = makeConfig();
    const html = await renderPage(config, "index", {
      site: { title: "My Site", url: "http://localhost" },
      pages: [],
      tags: [],
    });
    expect(html).toContain("My Site");
  });
});
