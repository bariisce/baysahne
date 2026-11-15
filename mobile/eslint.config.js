// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require("eslint/config");
const expoConfig = require("eslint-config-expo/flat");

module.exports = defineConfig([
  expoConfig,
  { ignores: ["dist/*", ".expo/*", "android/*", "ios/*"] },
  // TypeScript already verifies named imports; this rule misreads re-exported enums (expo-notifications).
  { files: ["**/*.ts", "**/*.tsx"], rules: { "import/namespace": "off" } },
  // app.config.ts runs in Node at build time, where dynamic env access is intended.
  { files: ["app.config.ts"], rules: { "expo/no-dynamic-env-var": "off" } },
  { files: ["**/__tests__/**"], rules: { "@typescript-eslint/no-require-imports": "off" } },
]);
