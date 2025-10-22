const { FusesPlugin } = require("@electron-forge/plugin-fuses");
const { FuseV1Options, FuseVersion } = require("@electron/fuses");

module.exports = {
  packagerConfig: {
    asar: true,
    extraResource: [
      "../backend/dist/backend"
    ],
    // Personnalisation de l'application
    name: "erudi",
    executableName: "erudi",
    appBundleId: "com.erudi.app",
    appCategoryType: "public.app-category.productivity",
    // Icône de l'application
    icon: "./assets/icons/icon",
    // Métadonnées de l'application
    appCopyright: "Copyright © 2025 Erudi Team",
    appVersion: "1.0.0",
    buildVersion: "1.0.0",
    
    // macOS Code Signing & Notarization
    ...(process.env.APPLE_SIGNING_IDENTITY && {
      osxSign: {
        identity: process.env.APPLE_SIGNING_IDENTITY,
        hardenedRuntime: true,
        entitlements: "./entitlements.plist",
        entitlementsInherit: "./entitlements.plist",
        gatekeeper: false,
      },
    }),
    ...(process.env.APPLE_ID && {
      osxNotarize: {
        tool: "notarytool",
        appleId: process.env.APPLE_ID,
        appleIdPassword: process.env.APPLE_ID_PASSWORD,
        teamId: process.env.APPLE_TEAM_ID,
      },
    }),
  },
  rebuildConfig: {},
  makers: [
    {
      name: "@electron-forge/maker-squirrel",
      config: {},
    },
    {
      name: "@electron-forge/maker-zip",
      platforms: ["darwin"],
    },
    {
      name: "@electron-forge/maker-dmg",
      config: {
        name: "erudi-Installer",
        icon: "./assets/icons/icon.icns",
        background: "./assets/dmg-background.png", 
        format: "UDZO",
        window: {
          x: 420,
          y: 200,
          width: 640,
          height: 440
        },
        contents: [
          {
            x: 200,
            y: 200,
            type: "file",
            path: "./out/erudi-darwin-arm64/erudi.app"
          },
          {
            x: 400,
            y: 200,
            type: "link",
            path: "/Applications"
          }
        ],
        iconSize: 80,
        textColor: "#FFFFFF"
      }
    },
    {
      name: "@electron-forge/maker-deb",
      config: {},
    },
    {
      name: "@electron-forge/maker-rpm",
      config: {},
    },
  ],
  plugins: [
    {
      name: "@electron-forge/plugin-auto-unpack-natives",
      config: {},
    },
    {
      name: "@electron-forge/plugin-webpack",
      config: {
        mainConfig: "./webpack.main.config.js",
        renderer: {
          config: "./webpack.renderer.config.js",
          entryPoints: [
            {
              html: "./public/index.html",
              js: "./src/renderer.js",
              name: "main_window",
              preload: {
                js: "./src/preload.js",
              },
            },
          ],
        },
      },
    },
    // Fuses are used to enable/disable various Electron functionality
    // at package time, before code signing the application
    new FusesPlugin({
      version: FuseVersion.V1,
      [FuseV1Options.RunAsNode]: false,
      [FuseV1Options.EnableCookieEncryption]: true,
      [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
      [FuseV1Options.EnableNodeCliInspectArguments]: false,
      [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
      [FuseV1Options.OnlyLoadAppFromAsar]: true,
    }),
  ],
};
