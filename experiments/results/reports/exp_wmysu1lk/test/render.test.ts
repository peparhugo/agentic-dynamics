import { describe, it, expect } from "vitest";
import path from "node:path";
import { renderTemplate, registerPartials } from "../src/render";

const templateDir = path.resolve(
  path.join(__dirname, "fixtures", "templates")
);

describe("renderTemplate", () => {
  it("renders index template with posts and partials", () => {
    const html = renderTemplate(templateDir, "index", {
      site: { title: "My Site", description: "", url: "", author: "Me" },
      posts: [
        {
          title: "Hello",
          date: "2024-01-01",
          slug: "hello",
          tags: ["intro"],
          content: "",
          draft: false,
          excerpt: "",
        },
      ],
      tags: [],
    });

    expect(html).toContain("My Site");
    expect(html).toContain("Hello");
    expect(html).toContain("intro");
    expect(html).toContain("<nav>");
    expect(html).toContain('href="/tags/"');
    expect(html).toContain("<footer>&copy; Me</footer>");
  });

  it("renders post template with HTML content", () => {
    const html = renderTemplate(templateDir, "post", {
      site: { title: "Site", description: "", url: "", author: "" },
      posts: [],
      post: {
        title: "My Post",
        date: "2024-06-01",
        slug: "my-post",
        tags: ["js"],
        content: "<p>Hello</p>",
        draft: false,
        excerpt: "",
      },
      tags: [],
    });

    expect(html).toContain("My Post");
    expect(html).toContain("<p>Hello</p>");
    expect(html).toContain("js");
  });

  it("renders tags-index template", () => {
    const html = renderTemplate(templateDir, "tags-index", {
      site: { title: "Site", description: "", url: "", author: "" },
      posts: [],
      tags: [
        { name: "js", posts: [{ title: "P1", date: "", slug: "p1", tags: ["js"], content: "", draft: false, excerpt: "" }] },
        { name: "ts", posts: [] },
      ],
    });

    expect(html).toContain("Tags");
    expect(html).toContain("js (1)");
    expect(html).toContain("ts (0)");
  });

  it("throws on missing template", () => {
    expect(() =>
      renderTemplate(templateDir, "nonexistent", {
        site: { title: "", description: "", url: "", author: "" },
        posts: [],
        tags: [],
      })
    ).toThrow();
  });
});

describe("registerPartials", () => {
  it("registers partials from a directory", () => {
    const partialsDir = path.join(templateDir, "partials");
    registerPartials(partialsDir);

    // Re-render index to confirm partial is still registered
    const html = renderTemplate(templateDir, "index", {
      site: { title: "X", description: "", url: "", author: "" },
      posts: [],
      tags: [],
    });
    expect(html).toContain("<nav>");
  });

  it("does not throw on missing partials dir", () => {
    expect(() => registerPartials("/nonexistent/partials")).not.toThrow();
  });
});
