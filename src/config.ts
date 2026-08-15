import { Plugin } from './plugin';

export interface SSGConfig {
  contentDir?: string;
  outputDir?: string;
  templateDir?: string;
  plugins?: Plugin[];
}

let config: SSGConfig = {
  contentDir: './content',
  outputDir: './dist',
  plugins: []
};

export function setConfig(newConfig: Partial<SSGConfig>): void {
  config = {
    ...config,
    ...newConfig
  };
}

export function getConfig(): SSGConfig {
  return config;
}

export async function loadConfigFile(configPath: string): Promise<SSGConfig> {
  try {
    const configModule = await import(configPath);
    const loadedConfig = configModule.default || configModule;
    setConfig(loadedConfig);
    return getConfig();
  } catch (error) {
    console.warn(`Could not load config from ${configPath}, using defaults`);
    return getConfig();
  }
}
