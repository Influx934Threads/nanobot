#!/usr/bin/env python3
"""
Privacy Filter Script

This script provides functionality to redact sensitive data before it reaches the LLM.
It can be used as a preprocessing layer for incoming messages, files, or other data.
"""

import re
import json
import logging
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class PrivacyFilter:
    def __init__(self, patterns_file: Optional[str] = None, replacements_file: Optional[str] = None):
        """
        Initialize the privacy filter with pattern and replacement files.
        
        Args:
            patterns_file: Path to patterns file (defaults to embedded patterns)
            replacements_file: Path to replacements file (defaults to embedded replacements)
        """
        self.patterns = self._load_patterns(patterns_file)
        self.replacements = self._load_replacements(replacements_file)
        self.reverse_mapping = {}  # For tracking what was redacted (if restoration needed)
        
    def _load_patterns(self, patterns_file: Optional[str] = None) -> Dict[str, List[Tuple[str, str]]]:
        """Load regex patterns for sensitive data detection."""
        if patterns_file and Path(patterns_file).exists():
            # Load from file
            patterns = {}
            current_category = None
            with open(patterns_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#') or not line:
                        continue
                    if line.endswith(':') and not line.startswith('-'):
                        current_category = line[:-1]
                        patterns[current_category] = []
                    elif line.startswith('- ') and current_category:
                        pattern = line[2:].strip()
                        patterns[current_category].append((pattern, current_category))
            return patterns
        else:
            # Return embedded patterns
            return {
                "Telegram Identifiers": [
                    (r'@[a-zA-Z][a-zA-Z0-9_]{4,31}', 'telegram_username'),
                    (r'(?<=user[:_]\s*)\b\d{5,15}\b', 'telegram_user_id'),
                    (r'(?<=chat[:_]\s*)-?\d{5,15}\b', 'telegram_chat_id'),
                    (r'\b\d{5,15}\b(?=\s*[:\-]\s*(?:user|chat|id))', 'contextual_numeric_id')
                ],
                "API Keys and Tokens": [
                    (r'sk-[a-zA-Z0-9]{20,}', 'openai_key'),
                    (r'sk-ant-[a-zA-Z0-9_-]{20,}', 'anthropic_key'),
                    (r'ghp_[a-zA-Z0-9]{36}', 'github_token'),
                    (r'github_pat_[a-zA-Z0-9_]+\w*', 'github_pat'),
                    (r'\d{8,10}:[a-zA-Z0-9_-]{35}', 'telegram_bot_token'),
                    (r'\b[A-Za-z0-9_-]{32,}\b', 'generic_api_key')
                ],
                "Personal Identifiers": [
                    (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 'email'),
                    (r'\b(?:\d{1,3}\.){3}\d{1,3}\b', 'ip_address'),
                    (r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', 'personal_name')
                ]
            }
    
    def _load_replacements(self, replacements_file: Optional[str] = None) -> Dict[str, str]:
        """Load replacement templates for redacted data."""
        if replacements_file and Path(replacements_file).exists():
            # Load from file
            replacements = {}
            with open(replacements_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#') or not line or ': ' not in line:
                        continue
                    key, value = line.split(': ', 1)
                    replacements[key] = value
            return replacements
        else:
            # Return embedded replacements
            return {
                'telegram_username': '[TELEGRAM_USER]',
                'telegram_user_id': '[TELEGRAM_ID]',
                'telegram_chat_id': '[TELEGRAM_CHAT_ID]',
                'contextual_numeric_id': '[NUMERIC_ID_REDACTED]',
                'openai_key': '[OPENAI_KEY_REDACTED]',
                'anthropic_key': '[ANTHROPIC_KEY_REDACTED]',
                'github_token': '[GITHUB_TOKEN_REDACTED]',
                'github_pat': '[GITHUB_TOKEN_REDACTED]',
                'telegram_bot_token': '[TELEGRAM_BOT_TOKEN_REDACTED]',
                'generic_api_key': '[API_KEY_REDACTED]',
                'email': '[EMAIL_REDACTED]',
                'ip_address': '[IP_ADDRESS_REDACTED]',
                'personal_name': '[PERSON_NAME_REDACTED]'
            }
    
    def filter_text(self, text: str, track_changes: bool = False) -> str:
        """
        Filter sensitive data from text.
        
        Args:
            text: Input text to filter
            track_changes: Whether to track what was redacted for potential restoration
            
        Returns:
            Filtered text with sensitive data replaced
        """
        if not text:
            return text
            
        filtered_text = text
        
        # Apply each pattern category
        for category, patterns in self.patterns.items():
            for pattern, pattern_type in patterns:
                def replace_func(match):
                    original = match.group(0)
                    replacement = self.replacements.get(pattern_type, f'[{pattern_type.upper()}_REDACTED]')
                    
                    if track_changes:
                        # Store mapping for potential restoration
                        if replacement not in self.reverse_mapping:
                            self.reverse_mapping[replacement] = []
                        if original not in self.reverse_mapping[replacement]:
                            self.reverse_mapping[replacement].append(original)
                    
                    logger.debug(f"Redacted {pattern_type}: {original[:20]}... -> {replacement}")
                    return replacement
                
                filtered_text = re.sub(pattern, replace_func, filtered_text, flags=re.IGNORECASE)
        
        return filtered_text
    
    def filter_json(self, data: Any, track_changes: bool = False) -> Any:
        """
        Filter sensitive data from JSON-like structures.
        
        Args:
            data: JSON data (dict, list, or primitive)
            track_changes: Whether to track what was redacted
            
        Returns:
            Filtered JSON data
        """
        if isinstance(data, dict):
            return {key: self.filter_json(value, track_changes) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.filter_json(item, track_changes) for item in data]
        elif isinstance(data, str):
            return self.filter_text(data, track_changes)
        else:
            return data  # Numbers, booleans, None remain unchanged
    
    def filter_file(self, file_path: str, output_path: Optional[str] = None, track_changes: bool = False) -> str:
        """
        Filter sensitive data from a file.
        
        Args:
            file_path: Path to input file
            output_path: Path to output file (if None, overwrites input)
            track_changes: Whether to track what was redacted
            
        Returns:
            Path to filtered file
        """
        if output_path is None:
            output_path = file_path
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        filtered_content = self.filter_text(content, track_changes)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(filtered_content)
        
        logger.info(f"Filtered file: {file_path} -> {output_path}")
        return output_path
    
    def get_mapping(self) -> Dict[str, List[str]]:
        """Get the mapping of redacted values to original values (if tracking enabled)."""
        return self.reverse_mapping.copy()
    
    def clear_mapping(self):
        """Clear the tracking mapping."""
        self.reverse_mapping.clear()

# Convenience functions for easy usage
def filter_text(text: str, track_changes: bool = False) -> str:
    """Convenience function to filter text using default filter."""
    pf = PrivacyFilter()
    return pf.filter_text(text, track_changes)

def filter_json(data: Any, track_changes: bool = False) -> Any:
    """Convenience function to filter JSON using default filter."""
    pf = PrivacyFilter()
    return pf.filter_json(data, track_changes)

def filter_file(file_path: str, output_path: Optional[str] = None, track_changes: bool = False) -> str:
    """Convenience function to filter file using default filter."""
    pf = PrivacyFilter()
    return pf.filter_file(file_path, output_path, track_changes)

if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python filter.py <text_or_file> [--track]")
        sys.exit(1)
    
    input_data = sys.argv[1]
    track_changes = '--track' in sys.argv
    
    # Try to treat as file first
    try:
        with open(input_data, 'r') as f:
            content = f.read()
        filtered = filter_file(input_data, track_changes=track_changes)
        print(f"Filtered file saved to: {filtered}")
    except FileNotFoundError:
        # Treat as text
        filtered = filter_text(input_data, track_changes=track_changes)
        print("Original:", input_data)
        print("Filtered:", filtered)
        
        pf = PrivacyFilter()
        if track_changes:
            mapping = pf.get_mapping()
            if mapping:
                print("\nRedaction mapping:")
                for redacted, originals in mapping.items():
                    print(f"  {redacted} -> {originals}")