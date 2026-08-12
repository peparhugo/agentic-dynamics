declare module 'gray-matter' {
  interface GrayMatterResult {
    content: string;
    data: Record<string, unknown>;
  }
  interface GrayMatterOptions {
    // no-op placeholder for forward compatibility
  }
  export default function matter(
    input: string,
    options?: GrayMatterOptions
  ): GrayMatterResult;
}
