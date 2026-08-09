import { describe, it, expect, beforeEach } from "vitest";
import path from "node:path";
import fs from "node:fs";
import os from "node:os";
import { HandlebarsTemplateEngine } from "../src/templates";
import { TemplateContext } from "../src/types";

describe("HandlebarsTemplateEngine", () => {
  let tmpDir: string;
  let engine: HandlebarsTemplateEngine;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "statico-test-"));
    fs.mkdirSync(path.join(tmpDir, "layouts"), { recursive: true });
    fs.mkdirSync(path.join(tmpDir, "partials"), { recursive: true });

    fs.writeFileSync(path.join(tmpDir, "layouts", "default.hbs"), `<html><body>{{> header}}{{{body}}}</body></html>`);
    fs.writeFileSync(path.join(tmpDir, "partials", "header.hbs"), `<header>{{site.title}}</header>`);
    fs.writeFileSync(path.join(tmpDir, "post.hbs"), `<article>{{{page.html}}}<span>{{page.frontmatter.title}}</span></article>`);
    fs.writeFileSync(path.join(tmpDir, "index.hbs"), `<ul>{{#each pages}}<li>{{frontmatter.title}}</li>{{/each}}</ul>`);

    engine = new HandlebarsTemplateEngine(tmpDir);
  });

  it("renders a page template within a layout", () => {
    const context: TemplateContext = {
      page: {
        frontmatter: { title: "Test Post", layout: "default" },
        html: "<p>Body content</p>",
        content: "",
        slug: "test-post",
        sourcePath: "",
      },
      site: { title: "My Site", url: "" },
    };
    const result = engine.render("post", context);
    expect(result).toContain("<header>My Site</header>");
    expect(result).toContain("Body content");
    expect(result).toContain("Test Post");
    expect(result).toContain("<html>");
  });

  it("renders index template with pages list", () => {
    const context: TemplateContext = {
      pages: [
        { frontmatter: { title: "Page 1" }, html: "", content: "", slug: "p1", sourcePath: "" },
        { frontmatter: { title: "Page 2" }, html: "", content: "", slug: "p2", sourcePath: "" },
      ],
      site: { title: "Site", url: "" },
    };
    const result = engine.render("index", context);
    expect(result).toContain("<li>Page 1</li>");
    expect(result).toContain("<li>Page 2</li>");
  });

  it("falls back to no layout when layout not found", () => {
    const context: TemplateContext = {
      page: {
        frontmatter: { title: "No Layout", layout: "nonexistent" },
        html: "<p>Content</p>",
        content: "",
        slug: "nl",
        sourcePath: "",
      },
      site: { title: "Site", url: "" },
    };
    const result = engine.render("post", context);
    expect(result).toContain("Content");
    expect(result).not.toContain("<html>");
  });

  it("throws for missing template", () => {
    expect(() => engine.render("nonexistent", { site: { title: "", url: "" } })).toThrow();
  });

  it("partials are accessible in templates", () => {
    const context: TemplateContext = {
      page: {
        frontmatter: { title: "Test", layout: "default" },
        html: "",
        content: "",
        slug: "",
        sourcePath: "",
      },
      site: { title: "Partials Site", url: "" },
    };
    const result = engine.render("post", context);
    expect(result).toContain("<header>Partials Site</header>");
  });

  it("renderString compiles and renders inline template", () => {
    const result = engine.renderString("Hello {{name}}!", {
      name: "World",
      site: { title: "", url: "" },
    });
    expect(result).toBe("Hello World!");
  });

  it("clearCache reloads templates", () => {
    fs.writeFileSync(path.join(tmpDir, "post.hbs"), `<div>CHANGED {{{page.html}}}</div>`);
    engine.clearCache();
    const context: TemplateContext = {
      page: {
        frontmatter: { title: "Test", layout: "default" },
        html: "<p>X</p>",
        content: "",
        slug: "",
        sourcePath: "",
      },
      site: { title: "Site", url: "" },
    };
    const result = engine.render("post", context);
    expect(result).toContain("CHANGED");
  });
});
