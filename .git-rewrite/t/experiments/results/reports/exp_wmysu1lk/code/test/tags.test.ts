import { describe, it, expect } from "vitest";
import { buildTagIndex, tagsTemplateData } from "../src/tags";
import { Post } from "../src/types";

const posts: Post[] = [
  {
    title: "Post A",
    date: "2024-02-01",
    slug: "post-a",
    tags: ["js", "ts"],
    content: "",
    draft: false,
    excerpt: "",
  },
  {
    title: "Post B",
    date: "2024-01-01",
    slug: "post-b",
    tags: ["js"],
    content: "",
    draft: false,
    excerpt: "",
  },
  {
    title: "Post C",
    date: "2024-03-01",
    slug: "post-c",
    tags: [],
    content: "",
    draft: false,
    excerpt: "",
  },
];

describe("buildTagIndex", () => {
  it("groups posts by tag", () => {
    const index = buildTagIndex(posts);
    expect(index.get("js")).toHaveLength(2);
    expect(index.get("ts")).toHaveLength(1);
    expect(index.get("nonexistent")).toBeUndefined();
  });

  it("sorts posts by date descending within each tag", () => {
    const index = buildTagIndex(posts);
    const jsPosts = index.get("js")!;
    expect(jsPosts[0].title).toBe("Post A");
    expect(jsPosts[1].title).toBe("Post B");
  });
});

describe("tagsTemplateData", () => {
  it("converts Map to sorted template data", () => {
    const index = buildTagIndex(posts);
    const data = tagsTemplateData(index);
    // "js" should come before "ts" alphabetically
    expect(data[0].name).toBe("js");
    expect(data[0].posts).toHaveLength(2);
    expect(data[1].name).toBe("ts");
    expect(data[1].posts).toHaveLength(1);
  });
});
