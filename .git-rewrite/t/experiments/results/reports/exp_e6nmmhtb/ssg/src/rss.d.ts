declare module "rss" {
  interface RSSItemOptions {
    title: string;
    description: string;
    url: string;
    guid?: string;
    categories?: string[];
    author?: string;
    date?: string;
    lat?: number;
    long?: number;
    enclosure?: { url: string; size?: number; type?: string };
    custom_elements?: Array<{ [key: string]: unknown }>;
  }

  interface RSSOptions {
    title: string;
    description: string;
    feed_url: string;
    site_url: string;
    image_url?: string;
    docs?: string;
    managingEditor?: string;
    webMaster?: string;
    copyright?: string;
    language?: string;
    categories?: string[];
    pubDate?: string;
    ttl?: number;
    hub?: string;
    custom_namespaces?: Record<string, string>;
    custom_elements?: Array<{ [key: string]: unknown }>;
  }

  class RSS {
    constructor(options: RSSOptions);
    item(options: RSSItemOptions): void;
    xml(options?: { indent?: boolean }): string;
  }

  export = RSS;
}
