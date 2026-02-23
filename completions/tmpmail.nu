# Universal Temporary Email Client - Link Extractor
export extern tmpmail [
    --version(-v)           # Show version information
    --log-level: string     # Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    --log-file: path        # Log to specified file
    --quiet(-q)             # Suppress console output
]

# Create a new email account
export extern "tmpmail new" [
    service: string@services # Email service to use
    --name: string           # Custom name for email address
    --pattern: string        # Custom regex pattern for link extraction
    --timeout: int           # Stop monitoring after N seconds (default: 300)
    --domain: string@domains # Domain for XTempMail (only valid with xtempmail)
    --local-part: string     # Custom local part for Guerrilla Mail
]

# List existing accounts
export extern "tmpmail list" [
    service?: string@services # Filter by service
    --count(-c): int          # Number of accounts to show (default: 10)
]

# Use an existing account
export extern "tmpmail use" [
    index: int               # Account index from list command
    --service: string@services # Filter by service when selecting index
    --pattern: string        # Custom regex pattern for link extraction
    --timeout: int           # Stop monitoring after N seconds
]

# List available email services
export extern "tmpmail services" []

# Custom completion helpers
def services [] { [xtempmail mailtm guerrilla] }
def domains [] { [mailto.plus fexpost.com fexbox.org mailbok.in.ua chitthi.in fextemp.com any.pink merepost.com] }
