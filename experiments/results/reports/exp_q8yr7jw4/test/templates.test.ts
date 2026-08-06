import { describe, it, expect, beforeEach } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { TemplateEngine } from "../src/templates.js";
import { makeTmpDir, writeTree, BASIC_TEMPLATES } from "./helpers.js";

describe("TemplateEngine", () => {
  let dir: string;

  beforeEach(() => {
    dir = makeTmpDir();
    writeTree(dir, BASIC_TEMPLATES);
  });

  it("renders a page template with context", () => {
    const engine = new TemplateEngine(dir);
    const html = engine.render("post", { title: "Hi", content: "<p>Body</p>", site: { title: "Site" } });
    expect(html).toContain("<h1>Hi</h1>");
    expect(html).toContain("<p>Body</p>");
  });

  it("renders partials", () => {
    const engine = new TemplateEngine(dir);
    const html = engine.render("post", { title: "T", content: "", site: { title: "My Blog" } });
    expect(html).toContain("<header>My Blog</header>");
  });

  it("wraps output in the default layout, exposing {{{body}}}", () => {
    const engine = new TemplateEngine(dir);
    const html = engine.render("post", { title: "Page Title", content: "<p>x</p>", site: {} });
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("<title>Page Title</title>");
    expect(html).toContain("<article>");
  });

  it("uses a named layout when given", () => {
    writeTree(dir, { "layouts/bare.hbs": "<main>{{{body}}}</main>" });
    const engine = new TemplateEngine(dir);
    const html = engine.render("post", { title: "T", content: "", site: {} }, "bare");
    expect(html).toContain("<main>");
    expect(html).not.toContain("<!DOCTYPE html>");
  });

  it("throws for a missing named layout", () => {
    const engine = new TemplateEngine(dir);
    expect(() => engine.render("post", {}, "nope")).toThrow(/Layout not found/);
  });

  it("renders without a layout if no default layout exists", () => {
    fs.rmSync(path.join(dir, "layouts"), { recursive: true });
    const engine = new TemplateEngine(dir);
    const html = engine.render("post", { title: "T", content: "<p>x</p>", site: {} });
    expect(html).not.toContain("<!DOCTYPE html>");
    expect(html).toContain("<h1>T</h1>");
  });

  it("throws for an unknown page template", () => {
    const engine = new TemplateEngine(dir);
    expect(() => engine.render("missing", {})).toThrow(/Template not found/);
  });

  it("throws for a missing template directory", () => {
    expect(() => new TemplateEngine(path.join(dir, "nope"))).toThrow(/Template directory not found/);
  });

  it("provides formatDate, eq, and join helpers", () => {
    writeTree(dir, {
      "helpers.hbs": "{{formatDate date}}|{{formatDate date 'iso'}}|{{#if (eq a 'x')}}yes{{/if}}|{{join list '+'}}",
    });
    const engine = new TemplateEngine(dir);
    const html = engine.render("helpers", { date: new Date("2024-03-15T12:00:00Z"), a: "x", list: ["a", "b"] });
    expect(html).toBe("2024-03-15|2024-03-15T12:00:00.000Z|yes|a+b");
  });

  it("reload() picks up template changes", () => {
    const engine = new TemplateEngine(dir);
    writeTree(dir, { "post.hbs": "CHANGED {{title}}" });
    expect(engine.render("post", { title: "T", content: "", site: {} })).not.toContain("CHANGED");
    engine.reload();
    expect(engine.render("post", { title: "T", content: "", site: {} })).toContain("CHANGED T");
  });
});
