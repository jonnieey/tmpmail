# tmpmail

**tmpmail** is a universal Command Line Interface (CLI) for managing temporary email accounts from multiple providers. It allows you to create disposable email addresses, monitor them for incoming messages in real-time, and automatically extract and open links (e.g., verification links).

## Features

- 🚀 **Multiple Services**: Supports **MailTM** and **XTempMail**.
- 📥 **Real-time Monitoring**: Watch for new emails instantly.
- 🔗 **Smart Link Extraction**: Automatically extracts links from emails matching a regex pattern (useful for confirmation emails).
- 📋 **Clipboard Integration**: Automatically copies new email addresses and extracted links to your clipboard.
- 🌐 **Browser Integration**: Automatically opens extracted links in your default browser.
- 💾 **Persistence**: Saves your recent accounts locally so you can reuse them later.
- 🛠️ **Customizable**: Configurable link patterns, timeout durations, and browser selection.

## Installation

### From Source

Ensure you have Python 3.8+ installed.

```bash
git clone https://github.com/jonnieey/tmpmail.git
cd tmpmail
pip install .
```

### Dependencies

*   `aiohttp`
*   `pyperclip`
*   `pydantic`
*   `xdg`
*   `mailtmapi`
*   `xtempmail`

## Usage

The main command is `tmpmail`. You can use the `--help` flag with any command to see more details.

```bash
tmpmail --help
```

### 1. Check Available Services

List all supported email providers:

```bash
tmpmail services
```

### 2. Create a New Account

Create a new temporary email address.

**Basic usage:**
```bash
tmpmail new mailtm
```

**With XTempMail (Custom Domain & Name):**
```bash
# List available domains for xtempmail (see --help for list or just try one)
tmpmail new xtempmail --domain mailto.plus --name mycustomuser
```

**Options:**
- `--name`: specific username (if supported by service).
- `--pattern`: Custom regex to extract specific links (default looks for generic URLs).
- `--timeout`: Stop monitoring after N seconds (default: 300).
- `--domain`: (XTempMail only) Choose a specific domain.

### 3. Monitor & Extract Links

Once an account is created (or reused), `tmpmail` starts monitoring.
- It waits for new emails.
- When an email arrives, it scans the content for links matching the configured pattern.
- If found, it **copies the link to the clipboard** and **opens it in your browser**.

**Custom Link Pattern Example:**
To only match links containing "verify":
```bash
tmpmail new mailtm --pattern "https?://[^\\s]*verify[^\\s]*"
```

### 4. List Recent Accounts

View your previously created accounts:

```bash
tmpmail list

# Filter by service
tmpmail list mailtm
```

### 5. Reuse an Account

Reconnect to a previously created account to check for more emails.

```bash
# Use the most recent account (index 1)
tmpmail use 1

# Use the 2nd most recent account
tmpmail use 2

# Filter by service
tmpmail use 1 --service xtempmail
```

## Configuration

You can configure `tmpmail` using environment variables:

| Variable | Description |
|----------|-------------|
| `TMPMAIL_LINK_PATTERN` | Default regex pattern for link extraction. |
| `BROWSER` or `PRIVATE_BROWSER` | Command to open links (defaults to `xdg-open`). |
| `XDG_DATA_HOME` | Directory to store account data (defaults to `~/.local/share`). |

## Storage

Account data is stored locally in JSON format at:
`~/.local/share/tempmail/accounts.json` (on Linux)

## License

MIT License

## Authors

- jonnieey
