import { defineConfig } from '@rspack/cli';
import { withZephyr } from 'zephyr-rspack-plugin';
import { rspack, type SwcLoaderOptions } from '@rspack/core';
// import { ReactRefreshRspackPlugin } from '@rspack/plugin-react-refresh';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);
const { ModuleFederationPlugin } = rspack.container;
const isDev = process.env.NODE_ENV === 'development';
const targets = ['last 2 versions', '> 0.2%', 'not dead', 'Firefox ESR'];

// Remote URL - change this to your deployed remote URL
const REMOTE_URL = process.env.REMOTE_URL || 'http://localhost:3001';

export default withZephyr()(
  defineConfig({
    entry: {
      index: './src/index.tsx',
    },
    devServer: {
      port: 3000,
    },
    resolve: {
      extensions: ['.ts', '.tsx', '.jsx', '.js', '.json'],
      alias: {
        scheduler: require.resolve('scheduler'),
      },
    },
    output: {
      publicPath: 'auto',
      chunkFilename: '[name].[contenthash].js',
    },
    module: {
      rules: [
        {
          test: /\.svg$/,
          type: 'asset',
        },
        {
          test: /\.(jsx?|tsx?)$/,
          use: [
            {
              loader: 'builtin:swc-loader',
              options: {
                jsc: {
                  parser: {
                    syntax: 'typescript',
                    tsx: true,
                  },
                  transform: {
                    react: {
                      runtime: 'automatic',
                    },
                  },
                },
                env: {
                  targets,
                },
              } satisfies SwcLoaderOptions,
            },
          ],
        },
      ],
    },
    plugins: [
      new rspack.HtmlRspackPlugin({
        template: './src/index.html',
      }),
      // React Refresh disabled due to workspace resolution issues
      // isDev ? new ReactRefreshRspackPlugin() : null,
      // Module Federation - Host configuration
      new ModuleFederationPlugin({
        name: 'mf_host',
        filename: 'remoteEntry.js',
        manifest: true,
        remotes: {
          // Remote app - will use fallback for ui-lib since host doesn't share it
          remote: `mf_react_treeshake@${REMOTE_URL}/remoteEntry.js`,
        },
        shared: {
          // Only share react/react-dom, NOT ui-lib
          // This forces the remote to use its fallback file for ui-lib
          react: {
            singleton: true,
            eager: true,
            requiredVersion: '^19.0.0',
          },
          'react-dom': {
            singleton: true,
            eager: true,
            requiredVersion: '^19.0.0',
          },
          // ui-lib is intentionally NOT shared here
          // This triggers fallback usage in the remote
        },
      }),
    ],
    optimization: {
      minimize: !isDev,
      chunkIds: 'named',
      moduleIds: 'named',
      minimizer: [
        new rspack.SwcJsMinimizerRspackPlugin(),
        new rspack.LightningCssMinimizerRspackPlugin({
          minimizerOptions: {
            targets,
          },
        }),
      ],
    },
    experiments: {
      css: true,
    },
  })
);
