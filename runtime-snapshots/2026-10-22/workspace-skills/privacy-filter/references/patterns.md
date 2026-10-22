# Privacy Filtering Patterns

This file contains regex patterns used to identify sensitive data that should be redacted before LLM processing.

## Telegram Identifiers
- Telegram usernames: `@[a-zA-Z][a-zA-Z0-9_]{4,31}`
- Telegram user IDs (numeric): `\b\d{5,15}\b` (when in context of Telegram)
- Telegram chat IDs: `^-?\d{5,15}$`

## API Keys and Tokens
- Generic API keys: `\b[A-Za-z0-9_-]{20,}\b`
- OpenAI API keys: `sk-[a-zA-Z0-9]{20,}`
- Anthropic API keys: `sk-ant-[a-zA-Z0-9_-]{20,}`
- GitHub tokens: `ghp_[a-zA-Z0-9]{36}` or `github_pat_[a-zA-Z0-9_]+\w*`
- Telegram bot tokens: `\d{8,10}:[a-zA-Z0-9_-]{35}`

## Personal Identifiers
- Email addresses: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
- IP addresses: `\b(?:\d{1,3}\.){3}\d{1,3}\b`
- Potential names in identifier context: `[A-Z][a-z]+ [A-Z][a-z]+` (when preceded/followed by ID-like patterns)

## Context-Sensitive Patterns
These patterns are applied with additional context checking to avoid false positives:
- Numbers that appear after labels like "id:", "user:", "chat:" 
- Patterns that appear in JSON/XML fields named "id", "userId", "chatId", etc.

## Usage Notes
Patterns should be tested thoroughly as over-matching can break functionality.
Consider the trade-off between privacy protection and data utility.