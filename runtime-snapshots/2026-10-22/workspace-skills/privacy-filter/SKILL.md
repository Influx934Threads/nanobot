---
name: privacy-filter
description: Privacy filtering system to redact sensitive data before LLM processing
---

# Privacy Filter

This skill provides tools and patterns for redacting sensitive information before it reaches the LLM processing layer, ensuring user privacy is maintained.

## Why Privacy Filtering Matters

Sensitive data like user IDs, chat IDs, API keys, and personal identifiers should not be processed by or stored in LLM systems. This skill helps prevent accidental exposure of such data.

## Features

- **Pattern-based redaction**: Identifies and redacts common sensitive patterns
- **Configurable rules**: Easy to add new patterns for different data types
- **Audit logging**: Tracks what was redacted for transparency
- **Reversible mapping**: Optionally maintains mapping for legitimate use cases

## Installation

The skill is already installed in your workspace at `~/.nanobot/workspace/skills/privacy-filter/`.

## Usage

### Redacting Text

Use the provided scripts to redact sensitive information:

```bash
# Redact a text file
python3 scripts/redact.py input.txt output.txt

# Redact stdin/stdout
echo "My user ID is @ciberjos" | python3 scripts/redact.py
```

### Patterns Currently Supported

- Telegram user IDs: `@username` format
- Telegram chat IDs: numeric identifiers
- API keys: common patterns for various services
- Email addresses
- IP addresses
- Personal names (basic patterns)

## Configuration

Edit `references/patterns.yaml` to customize what gets redacted:

```yaml
patterns:
  - name: "telegram_user"
    pattern: "@[a-zA-Z][a-zA-Z0-9_]{4,31}"
    replacement: "[TELEGRAM_USER]"
    description: "Telegram usernames"
  
  - name: "telegram_chat_id"
    pattern: "\\b[0-9]{8,15}\\b"
    replacement: "[CHAT_ID]"
    description: "Telegram chat IDs"
```

## How It Works

1. **Preprocessing**: Text passes through filtering before LLM processing
2. **Pattern Matching**: Uses regex patterns to identify sensitive data
3. **Redaction**: Replaces matches with configurable placeholders
4. **Logging**: Optionally logs what was redacted for audit trails
5. **Processing**: Cleaned text goes to LLM for normal processing

## Integration Points

This skill is designed to be integrated at various points:
- **Input sanitization**: Before user messages reach LLM
- **Output filtering**: Before LLM responses are stored or displayed
- **Memory protection**: Before storing conversation history
- **Tool arguments**: Before passing data to external tools

## Maintenance

- Update patterns in `references/patterns.yaml` as needed
- Test new patterns with `scripts/test_patterns.py`
- Review audit logs in `logs/redaction.log` if enabled

## Example

Input: "Hi @ciberjos, my chat ID is 8281248569 and my API key is sk-1234567890abcdef"
Output: "Hi [TELEGRAM_USER], my chat ID is [CHAT_ID] and my API key is [API_KEY]"