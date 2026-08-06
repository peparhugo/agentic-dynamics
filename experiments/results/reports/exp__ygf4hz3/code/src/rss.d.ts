declare module 'rss' {
  interface RSSFeedOptions {
    title: string;
    description: string;
    feed_url?: string;
    site_url: string;
    language?: string;
    [key: string]: unknown;
  }

  interface RSSItemOptions {
    title: string;
    description: string;
    url: string;
    date?: string | Date;
    categories?: string[];
    [key: string]: unknown;
  }

  class RSS {
    constructor(options: RSSFeedOptions);
    item(options: RSSItemOptions): void;
    xml(options?: { indent?: boolean }): string;
  }

  export = RSS;
}
