import { defineConfig } from '@rspack/cli';
import { withZephyr } from "zephyr-rspack-plugin";
import { rspack, type SwcLoaderOptions } from '@rspack/core';
import { ReactRefreshRspackPlugin } from '@rspack/plugin-react-refresh';
const {
  ModuleFederationPlugin
} = rspack.container;
const isDev = process.env.NODE_ENV === 'development';
const targets = ['last 2 versions', '> 0.2%', 'not dead', 'Firefox ESR'];
export default withZephyr()(defineConfig({
  entry: {
    index: './src/index.tsx'
  },
  resolve: {
    extensions: ['.ts', '.tsx', '.jsx']
  },
  output: {
    publicPath: 'auto',
    chunkFilename: '[name].[contenthash].js'
  },
  module: {
    rules: [{
      test: /\.svg$/,
      type: 'asset'
    }, {
      test: /\.(jsx?|tsx?)$/,
      use: [{
        loader: 'builtin:swc-loader',
        options: {
          jsc: {
            parser: {
              syntax: 'typescript',
              tsx: true
            },
            transform: {
              react: {
                runtime: 'automatic',
                development: isDev,
                refresh: isDev
              }
            }
          },
          env: {
            targets
          }
        } satisfies SwcLoaderOptions
      }]
    }]
  },
  plugins: [new rspack.HtmlRspackPlugin({
    template: './src/index.html'
  }), isDev ? new ReactRefreshRspackPlugin() : null,
  // Module Federation with tree-shaking shared
  new ModuleFederationPlugin({
    name: 'mf_react_treeshake',
    filename: 'remoteEntry.js',
    manifest: true,
    exposes: {
      './App': './src/App.tsx',
      './Button': './src/components/Button.tsx'
    },
    shared: {
      react: {
        singleton: true,
        requiredVersion: '^19.0.0',
        treeShaking: {
          mode: 'runtime-infer'
        }
      },
      'react-dom': {
        singleton: true,
        requiredVersion: '^19.0.0',
        treeShaking: {
          mode: 'runtime-infer'
        }
      },
      'ui-lib': {
        singleton: true,
        requiredVersion: '^1.0.0',
        treeShaking: {
          mode: 'runtime-infer'
        }
      }
    }
  })],
  optimization: {
    minimize: !isDev,
    chunkIds: 'named',
    moduleIds: 'named',
    minimizer: [new rspack.SwcJsMinimizerRspackPlugin(), new rspack.LightningCssMinimizerRspackPlugin({
      minimizerOptions: {
        targets
      }
    })]
  },
  experiments: {
    css: true
  }
}));