#!/usr/bin/env python3
"""
Privacy filtering script to redact sensitive data from text.
"""

import re
import sys
import yaml
import argparse
from pathlib import Path

def load_patterns(config_path=None):
    """Load redaction patterns from YAML config."""
    if config_path is None:
        config_path = Path(__file__).parent.parent / 'references' / 'patterns.yaml'
    
    default_patterns = [
        {
            'name': 'telegram_user',
            'pattern': r'@[a-zA-Z][a-zA-Z0-9_]{4,31}',
            'replacement': '[TELEGRAM_USER]',
            'description': 'Telegram usernames'
        },
        {
            'name': 'telegram_chat_id',
            'pattern': r'\b[0-9]{8,15}\b',
            'replacement': '[CHAT_ID]',
            'description': 'Telegram chat IDs'
        },
        {
            'name': 'api_key_generic',
            'pattern': r'\b[sk-|ak-][0-9a-zA-Z]{20,}\b',
            'replacement': '[API_KEY]',
            'description': 'Generic API keys'
        },
        {
            'name': 'email',
            'pattern': r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
            'replacement': '[EMAIL]',
            'description': 'Email addresses'
        },
        {
            'name': 'ip_address',
            'pattern': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            'replacement': '[IP_ADDRESS]',
            'description': 'IP addresses'
        }
    ]
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            if config and 'patterns' in config:
                return config['patterns']
    except FileNotFoundError:
        pass
    except yaml.YAMLError as e:
        print(f"Warning: Could not load patterns from {config_path}: {e}", file=sys.stderr)
    
    return default_patterns

def redact_text(text, patterns=None, audit_log=None):
    """Redact sensitive patterns in text."""
    if patterns is None:
        patterns = load_patterns()
    
    redacted = text
    redactions = []
    
    for pattern_info in patterns:
        pattern = pattern_info['pattern']
        replacement = pattern_info['replacement']
        name = pattern_info['name']
        
        matches = list(re.finditer(pattern, redacted))
        if matches:
            redacted = re.sub(pattern, replacement, redacted)
            for match in matches:
                redactions.append({
                    'type': name,
                    'original': match.group(),
                    'position': match.span()
                })
    
    if audit_log and redactions:
        with open(audit_log, 'a') as f:
            for redaction in redactions:
                f.write(f"{redaction['type']}:{redaction['original']}\n")
    
    return redacted, redactions

def main():
    parser = argparse.ArgumentParser(description='Redact sensitive data from text')
    parser.add_argument('input', nargs='?', type=argparse.FileType('r'), default=sys.stdin,
                       help='Input file (default: stdin)')
    parser.add_argument('output', nargs='?', type=argparse.FileType('w'), default=sys.stdout,
                       help='Output file (default: stdout)')
    parser.add_argument('--patterns', type=str, help='Path to patterns YAML file')
    parser.add_argument('--audit-log', type=str, help='Path to audit log file')
    parser.add_argument('--stats', action='store_true', help='Show redaction statistics')
    
    args = parser.parse_args()
    
    # Read input
    text = args.input.read()
    args.input.close()
    
    # Redact
    patterns = load_patterns(args.patterns) if args.patterns else None
    redacted_text, redactions = redact_text(text, patterns, args.audit_log)
    
    # Write output
    args.output.write(redacted_text)
    args.output.close()
    
    # Show stats if requested
    if args.stats and redactions:
        print(f"Redacted {len(redactions)} items:", file=sys.stderr)
        from collections import Counter
        counter = Counter(r['type'] for r in redactions)
        for type_name, count in counter.items():
            print(f"  {type_name}: {count}", file=sys.stderr)

if __name__ == '__main__':
    main()