# Apple Notarization Setup Guide for Erudi

This guide explains how to set up Apple code signing and notarization for your Erudi app.

## Prerequisites

1. **Apple Developer Account** - You must be a member of Apple Developer Program
2. **Mac with Xcode Command Line Tools** - `xcode-select --install`
3. **App-specific Password** - Generate from Apple ID account settings

## Step 1: Set Up Your Signing Certificate

### Get Your Signing Identity

1. Open **Keychain Access**
2. Go to **Certificate Assistant** → **Request a Certificate from a Certificate Authority**
3. Or download from [Apple Developer](https://developer.apple.com/account)
4. Look for "Developer ID Application" certificate

### Find Your Signing Identity

```bash
# List available signing identities
security find-identity -v -p codesigning
```

You'll see output like:
```
"Developer ID Application: Your Name (XXXXXXXXXX)"
```

Copy this exact string for `APPLE_SIGNING_IDENTITY` below.

## Step 2: Get Your Team ID

1. Go to [Apple Developer Account](https://developer.apple.com/account)
2. Navigate to **Membership**
3. Look for "Team ID" (10-character alphanumeric code)

## Step 3: Create App-Specific Password

1. Go to [appleid.apple.com](https://appleid.apple.com)
2. Sign in with your Apple ID
3. Go to **Security** tab
4. Under **App-Specific Passwords**, click **Generate password**
5. Choose "Other" and name it "Erudi Build"
6. Copy the generated password

## Step 4: Set Environment Variables

Create a `.env.notarize` file in your project root:

```bash
# Copy from your setup above
export APPLE_ID="your-apple-id@icloud.com"
export APPLE_ID_PASSWORD="xxxx-xxxx-xxxx-xxxx"  # App-specific password
export APPLE_TEAM_ID="XXXXXXXXXX"                # 10-char Team ID
export APPLE_SIGNING_IDENTITY="Developer ID Application: Your Name (XXXXXXXXXX)"
```

**Security Warning:** Never commit `.env.notarize` to git!

Add to `.gitignore`:
```
.env.notarize
```

## Step 5: Build with Notarization

### Option A: One-time Build

```bash
# Source the environment variables
source .env.notarize

# Build the app (will automatically sign and notarize)
./build-scripts/build-erudi.sh
```

### Option B: Persistent Session

```bash
# Add to your shell session
export APPLE_ID="your-apple-id@icloud.com"
export APPLE_ID_PASSWORD="xxxx-xxxx-xxxx-xxxx"
export APPLE_TEAM_ID="XXXXXXXXXX"
export APPLE_SIGNING_IDENTITY="Developer ID Application: Your Name (XXXXXXXXXX)"

# Then build normally
./build-scripts/build-erudi.sh
```

## Step 6: Verify Notarization

After the build completes:

```bash
# Check if the DMG is signed
codesign -vvv /path/to/erudi-Installer.dmg

# Verify notarization status
spctl -a -v -t install "/Volumes/erudi-Installer/erudi.app"

# Or check the notarization log
xcrun notarytool log <submission-id>
```

## What Happens During Build

1. **Code Signing** - Your app is signed with your Developer ID
2. **Entitlements** - Permissions are applied (network, file access, temp dirs)
3. **Hardened Runtime** - macOS security features are enabled
4. **Notarization** - Apple scans the app for malware
5. **Stapling** - Notarization ticket is attached to the app

## Troubleshooting

### "Code signing identity not found"
```bash
# Make sure your certificate is installed and not expired
security find-identity -v -p codesigning
```

### "Invalid password"
- Generate a new app-specific password
- Make sure there are no spaces or quotes in your `.env.notarize`

### "Notarization failed"
```bash
# Check the detailed error
xcrun notarytool log <submission-id> --keychain-profile default
```

### "Team ID mismatch"
- Verify your Team ID matches the one in your Developer ID certificate
- Check [developer.apple.com/account](https://developer.apple.com/account)

## Removing Notarization (Development)

If you don't want to notarize during development, just don't set the environment variables:

```bash
./build-scripts/build-erudi.sh --skip-backend
```

The build will skip notarization and produce an unsigned app (only for local testing).

## Resources

- [Apple Code Signing Overview](https://developer.apple.com/support/code-signing/)
- [Notarizing macOS Software](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [Hardened Runtime](https://developer.apple.com/documentation/security/hardened_runtime)
- [Electron Forge macOS Signing](https://www.electronforge.io/config/makers/dmg)

## Questions?

If you encounter issues, check:
1. Apple ID is correct
2. Team ID is correct (10 characters)
3. App-specific password was generated
4. Signing identity exists and isn't expired
5. Your Mac's date/time is correct (affects certificate validation)
