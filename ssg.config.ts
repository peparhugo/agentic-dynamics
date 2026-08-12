import { ExamplePlugin } from './plugins/example';

export interface SsgConfig {
  plugins: unknown[];
}

const config: SsgConfig = {
  plugins: [new ExamplePlugin()],
};

export default config;
