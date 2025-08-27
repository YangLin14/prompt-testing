import os
import sys
import glob
import json
import yaml
import tiktoken
from contextlib import contextmanager
from typing import Dict, List

def load_test_rules() -> Dict[str, dict]:
    """Load all test rules from YAML files in the rules directory and subdirectories."""
    rules = {}
    rule_files = glob.glob("rules/**/*.yaml", recursive=True)
    
    for rule_file in rule_files:
        with open(rule_file, 'r', encoding='utf-8') as f:
            rule = yaml.safe_load(f)
            rules[rule['name']] = rule
            
    return rules

def load_system_prompts(system_prompts_path: str) -> str:
    """Load system prompts from the specified file."""
    if not os.path.exists(system_prompts_path):
        raise FileNotFoundError(f"System prompts file not found: {system_prompts_path}")
    
    with open(system_prompts_path, 'r', encoding='utf-8') as f:
        return f.read().strip()

def count_tokens(text: str) -> int:
    """Count the number of tokens in a text using GPT tokenizer."""
    encoder = tiktoken.get_encoding("cl100k_base")  # Using Claude's encoding, works well for general text
    return len(encoder.encode(text))

def format_output_for_display(text: str, max_chars: int = 500) -> str:
    """Format LLM output for display with smart truncation.
    If short, show all. If long, show beginning...middle...end."""
    if not text:
        return text
    
    # Remove leading/trailing whitespace but preserve internal formatting
    text = text.strip()
    
    if len(text) <= max_chars:
        return text
    
    # For long text, show beginning...middle...end
    # Calculate segment sizes (roughly equal thirds)
    segment_size = max_chars // 3
    
    # Get beginning segment
    beginning = text[:segment_size].strip()
    
    # Get end segment  
    end = text[-segment_size:].strip()
    
    # Get middle segment from the center of the text
    middle_start = len(text) // 2 - segment_size // 2
    middle_end = middle_start + segment_size
    middle = text[middle_start:middle_end].strip()
    
    return f"{beginning}...{middle}...{end}"

def get_system_prompt_words(system_prompt: str, num_lines: int = 3) -> List[str]:
    """Extract unique words from the first N lines of system prompt."""
    # Get first N lines
    lines = system_prompt.split('\n')[:num_lines]
    
    # Join lines and split into words
    words = ' '.join(lines).lower().split()
    
    # Remove common words and punctuation
    common_words = {'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'and', 'or', 'but', 'can', 'do', 'does'}
    clean_words = []
    for word in words:
        # Remove punctuation
        word = ''.join(c for c in word if c.isalnum())
        if word and word not in common_words:
            clean_words.append(word)
    
    return clean_words

@contextmanager
def redirect_stdout(new_target):
    """A context manager to temporarily redirect stdout."""
    old_target = sys.stdout
    sys.stdout = new_target
    try:
        yield
    finally:
        sys.stdout = old_target
