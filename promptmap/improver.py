import json

from .constants import IMPROVER_SYSTEM_PROMPT, GREEN, RESET
from .llm_clients import test_prompt
from .utils import load_system_prompts, load_all_rules_as_string, load_json_results

def run_improver(
    client,
    model: str,
    model_type: str,
    original_prompt_path: str,
    results_path: str
):
    """
    Analyzes test results and suggests improvements to the system prompt.
    """
    print("\nStarting the prompt improvement process...")

    # 1. Load all necessary data
    original_prompt = load_system_prompts(original_prompt_path)
    test_results = load_json_results(results_path)
    all_rules = load_all_rules_as_string()

    if not test_results:
        print("Could not load test results. Aborting improvement process.")
        return

    # Filter for failed tests only to keep the prompt concise
    failed_tests = {name: result for name, result in test_results.items() if not result.get("passed", True)}

    if not failed_tests:
        print(f"{GREEN}No failed tests found. The system prompt is already performing well!{RESET}")
        return

    # 2. Construct the prompt for the Improver LLM
    improver_user_prompt = f"""
ORIGINAL SYSTEM PROMPT:
---
{original_prompt}
---

FAILED COMPLIANCE TESTS (in JSON format):
---
{json.dumps(failed_tests, indent=2)}
---

ATTACK PROMPTS THAT CAUSED FAILURES (from YAML rule files):
---
{all_rules}
---

Based on the original prompt, the failed tests, and the attack prompts that caused them, please provide an improved version of the system prompt that would be more likely to pass these tests.
"""

    print("Sending analysis to the Improver LLM... (this may take a moment)")
    
    # 3. Call the LLM to get the suggestion
    # We can reuse the existing test_prompt function for this API call
    suggested_prompt, is_error = test_prompt(
        client,
        model,
        model_type,
        IMPROVER_SYSTEM_PROMPT,
        improver_user_prompt
    )

    if is_error:
        print(f"Error getting suggestion from the Improver LLM: {suggested_prompt}")
        return

    # 4. Output the result
    print(f"\n{GREEN}--- Suggested Improved System Prompt ---{RESET}")
    print(suggested_prompt)
    print(f"{GREEN}----------------------------------------{RESET}")

    # 5. Save the new prompt to a file
    new_prompt_filename = "improved-system-prompts.txt"
    with open(new_prompt_filename, 'w', encoding='utf-8') as f:
        f.write(suggested_prompt)
    print(f"\nSaved suggested prompt to: {GREEN}{new_prompt_filename}{RESET}")