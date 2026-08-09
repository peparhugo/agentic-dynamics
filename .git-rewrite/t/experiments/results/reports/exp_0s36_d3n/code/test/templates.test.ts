import { describe, it, expect } from "vitest";
import path from "path";
import { createTemplateEngine } from "../src/templates";

const templateDir = path.join(__dirname, "fixtures", "templates");

describe("createTemplateEngine", () => {
  const engine = createTemplateEngine(templateDir);

  it("renders a simple template", () => {
    const html = engine.render("post", {
      title: "Test Post",
      content: "<p>Hello</p>",
      site: { title: "My Site", description: "", url: "" },
      pages: [],
      page: {},
    });
    expect(html).toContain("Test Post");
    expect(html).toContain("<p>Hello</p>");
  });

  it("renders custom formatDate helper", () => {
    const html = engine.render("post", {
      title: "Test",
      date: "2024-06-15",
      content: "",
      site: { title: "Site", description: "", url: "" },
      pages: [],
      page: {},
    });
    expect(html).toContain("June 15, 2024");
  });

  it("renders tags when present", () => {
    const html = engine.render("post", {
      title: "Test",
      tags: ["javascript", "typescript"],
      content: "",
      site: { title: "Site", description: "", url: "" },
      pages: [],
      page: {},
    });
    expect(html).toContain("/tags/javascript/");
    expect(html).toContain("/tags/typescript/");
    expect(html).toContain("javascript");
  });

  it("omits tags section when no tags", () => {
    const html = engine.render("post", {
      title: "Test",
      content: "",
      site: { title: "Site", description: "", url: "" },
      pages: [],
      page: {},
    });
    expect(html).not.toContain('class="tags"');
  });

  it("includes partials from partials/ directory", () => {
    const html = engine.renderWithLayout(
      "post",
      "layouts/default",
      {
        title: "Test",
        content: "<p>Body</p>",
        site: { title: "My Site", description: "", url: "" },
        pages: [],
        page: {},
      }
    );
    expect(html).toContain("<nav>");
    expect(html).toContain("Home");
    expect(html).toContain("Tags");
  });

  it("renderWithLayout wraps content in layout", () => {
    const html = engine.renderWithLayout(
      "post",
      "layouts/default",
      {
        title: "Layered",
        content: "<p>Body content</p>",
        site: { title: "Layered Site", description: "", url: "" },
        pages: [],
        page: {},
      }
    );
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("Layered Site");
    expect(html).toContain("<p>Body content</p>");
    expect(html).toContain("<footer>");
  });

  it("renderWithLayout passes title to layout", () => {
    const html = engine.renderWithLayout(
      "post",
      "layouts/default",
      {
        title: "Page Title",
        content: "",
        site: { title: "Site Title", description: "", url: "" },
        pages: [],
        page: {},
      }
    );
    expect(html).toContain("<title>Page Title - Site Title</title>");
  });

  it("throws for missing template", () => {
    expect(() =>
      engine.render("nonexistent", {})
    ).toThrow(/Template "nonexistent" not found/);
  });

  it("renders tag template", () => {
    const html = engine.render("tag", {
      title: 'Posts tagged "js"',
      tag: "js",
      posts: [
        {
          url: "/posts/hello/",
          frontmatter: { title: "Hello" },
        },
      ],
      site: { title: "Site", description: "", url: "" },
      pages: [],
    });
    expect(html).toContain("js");
    expect(html).toContain("/posts/hello/");
    expect(html).toContain("Hello");
  });
});
