const path = require("path");
const webpack = require("webpack");
const fs = require("fs");
const os = require("os");
const HtmlWebpackPlugin = require("html-webpack-plugin");

const isProduction = process.env.NODE_ENV === "production";

// Use office-addin-dev-certs trusted certificates for HTTPS
const getHttpsOptions = () => {
  const certDir = path.join(os.homedir(), ".office-addin-dev-certs");
  const certPath = path.join(certDir, "localhost.crt");
  const keyPath = path.join(certDir, "localhost.key");
  if (fs.existsSync(certPath) && fs.existsSync(keyPath)) {
    return { cert: fs.readFileSync(certPath), key: fs.readFileSync(keyPath) };
  }
  return {};
};

module.exports = {
  entry: {
    taskpane: "./src/taskpane/index.tsx",
    commands: "./src/commands/actions.ts",
    functions: "./src/functions/functions.ts",
  },
  output: {
    path: path.resolve(__dirname, "dist"),
    filename: "[name].bundle.js",
    clean: true,
  },
  resolve: {
    extensions: [".ts", ".tsx", ".js", ".jsx"],
  },
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        use: "ts-loader",
        exclude: /node_modules/,
      },
      {
        test: /\.css$/,
        use: ["style-loader", "css-loader"],
      },
      {
        test: /\.(png|jpe?g|gif|svg)$/i,
        type: "asset/resource",
        generator: {
          filename: "assets/[name][ext]",
        },
      },
    ],
  },
  plugins: [
    new HtmlWebpackPlugin({
      template: "./src/taskpane/index.html",
      filename: "taskpane.html",
      chunks: ["taskpane"],
    }),
    new HtmlWebpackPlugin({
      template: "./src/commands/commands.html",
      filename: "commands.html",
      chunks: ["commands"],
    }),
    new webpack.DefinePlugin({
      "process.env": JSON.stringify({}),
    }),
  ],
  devServer: {
    static: [
      { directory: path.resolve(__dirname, "dist") },
      { directory: path.resolve(__dirname, "src/assets"), publicPath: "/assets" },
    ],
    port: 3100,
    server: { type: "https", options: getHttpsOptions() },
    // CRITICAL: must be false — compression middleware buffers entire response
    // body before compressing, which completely kills SSE streaming.
    compress: false,
    headers: { "Access-Control-Allow-Origin": "*" },
    client: { overlay: false },
    proxy: [
      {
        context: ["/v1"],
        target: "http://localhost:8002",
        changeOrigin: true,
        secure: false,
        timeout: 5400000,      // 90 minutes — agent can run long with 1000 turns
        proxyTimeout: 5400000,
        // Required for SSE: disable proxy buffering so events stream through
        onProxyRes: function (proxyRes) {
          proxyRes.headers["cache-control"] = "no-cache";
          proxyRes.headers["x-accel-buffering"] = "no";
        },
      },
      {
        context: ["/api"],
        target: "http://localhost:8002",
        changeOrigin: true,
        secure: false,
        timeout: 300000,       // 5 minutes for regular API calls
        proxyTimeout: 300000,
      },
    ],
  },
  devtool: isProduction ? false : "source-map",
};
