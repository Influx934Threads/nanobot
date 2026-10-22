# Privacy Filter Replacement Templates

This file defines what sensitive data should be replaced with when detected by the privacy filter.

## Replacement Strategy

Use consistent, recognizable placeholders that:
1. Clearly indicate data has been redacted
2. Maintain data type/format expectations where possible
3. Allow for potential mapping restoration if needed
4. Are unlikely to appear naturally in text

## Telegram Identifiers
- Telegram usernames: `[TELEGRAM_USER]`
- Telegram user IDs: `[TELEGRAM_ID]`
- Telegram chat IDs: `[TELEGRAM_CHAT_ID]`

## API Keys and Tokens
- Generic API keys: `[API_KEY_REDACTED]`
- OpenAI API keys: `[OPENAI_KEY_REDACTED]`
- Anthropic API keys: `[ANTHROPIC_KEY_REDACTED]`
- GitHub tokens: `[GITHUB_TOKEN_REDACTED]`
- Telegram bot tokens: `[TELEGRAM_BOT_TOKEN_REDACTED]`

## Personal Identifiers
- Email addresses: `[EMAIL_REDACTED]`
- IP addresses: `[IP_ADDRESS_REDACTED]`
- Personal names: `[PERSON_NAME_REDACTED]`

## Context-Sensitive Replacements
For fields that need to maintain specific formats:
- Numeric IDs: `[NUMERIC_ID_REDACTED]`
- Alphanumeric IDs: `[ALPHANUMERIC_ID_REDACTED]`
- UUIDs: `[UUID_REDACTED]`

## Usage Guidelines

### Consistency
Use the same replacement for the same type of data throughout a document to maintain consistency.

### Context Awareness
Consider the surrounding context when choosing replacements:
- In JSON: maintain field names but replace values
- In logs: keep structural elements but redact sensitive values
- In code: preserve variable names but redact literal values

### Restoration Mapping
If data restoration is needed later, maintain a mapping table:
```
[TELEGRAM_USER] -> @actualusername
[TELEGRAM_ID] -> 123456789
[API_KEY_REDACTED] -> actual_key_value
```

This mapping should be stored securely and separately from filtered data.