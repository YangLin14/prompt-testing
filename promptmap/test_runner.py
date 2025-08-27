from typing import Dict

from .llm_clients import initialize_clients, test_prompt, validate_api_keys
from .evaluator import evaluate_test_result
from .utils import format_output_for_display, load_test_rules, load_system_prompts
from .constants import GREEN, RED, YELLOW, RESET

def run_single_test(target_client, target_model: str, target_model_type: str, 
                   controller_client, controller_model: str, controller_model_type: str, 
                   system_prompt: str, test_name: str, rule: dict, num_runs: int = 5,
                   firewall_mode: bool = False, pass_condition: str = None, fail_only: bool = False, debug_prompt_leak: bool = False) -> Dict:
    """Run a single test multiple times and evaluate results."""
    failed_result = None
    passed_count = 0
    
    for i in range(num_runs):
        if not fail_only:
            print(f"\n  --- Iteration {i+1}/{num_runs} ---")
        # print(f"    [DEBUG] Sending Attack Prompt to Target LLM (first 200 chars): {rule['prompt'][:200]}{'...' if len(rule['prompt']) > 200 else ''}")
        response, is_error = test_prompt(target_client, target_model, target_model_type, system_prompt, rule['prompt'])
        # print(f"    [DEBUG] Target LLM Response to Attack Prompt (first 200 chars): {response[:200]}{'...' if len(response) > 200 else ''}")
        passed, reason = evaluate_test_result(controller_client, controller_model, controller_model_type, test_name, rule, response, is_error, system_prompt, firewall_mode, pass_condition)
        
        if passed:
            passed_count += 1
            if not fail_only:
                print(f"    Result: {GREEN}PASS{RESET}")
                if response and not is_error:
                    formatted_response = format_output_for_display(response)
                    print(f"    LLM Output: {formatted_response}")
        else:
            failed_result = {
                "response": response,
                "reason": reason
            }
            # Always show the iteration header and result for failed tests
            if fail_only:
                print(f"\n  --- Iteration {i+1}/{num_runs} ---")
            
            if reason.startswith("API Error:"):
                print(f"    Result: {YELLOW}ERROR{RESET} - {reason}")
            else:
                print(f"    Result: {RED}FAIL{RESET} - {reason}")
                if response and not reason.startswith("API Error:"):
                    formatted_response = format_output_for_display(response)
                    print(f"    LLM Output: {formatted_response}")
            break  # Stop iterations on first failure
        
    overall_passed = passed_count == num_runs
    actual_runs = i + 1  # Number of actual iterations run
    
    result = {
        "type": rule['type'],
        "severity": rule['severity'],
        "passed": overall_passed,
        "pass_rate": f"{passed_count}/{actual_runs}"
    }
    
    # Only include failed result if there was a failure
    if failed_result:
        result["failed_result"] = failed_result
        
    return result

def run_tests(target_model: str, target_model_type: str, controller_model: str, controller_model_type: str, system_prompts_path: str, iterations: int = 5, severities: list = None, rule_names: list = None, rule_types: list = None, firewall_mode: bool = False, pass_condition: str = None, fail_only: bool = False, ollama_url: str = "http://localhost:11434") -> Dict[str, dict]:
    """Run all tests and return results."""
    print("\nTest started...")
    validate_api_keys(target_model_type, controller_model_type)
    target_client, controller_client = initialize_clients(target_model_type, controller_model_type, ollama_url)
    system_prompt = load_system_prompts(system_prompts_path)
    results = {}
    passed_results_count = 0
    
    if firewall_mode and not pass_condition:
        raise ValueError("Pass condition must be specified when using firewall mode")
    
    test_rules = load_test_rules()
    
    # Filter rules based on severity, rule names, and rule types
    filtered_rules = {}
    for test_name, rule in test_rules.items():
        # Check if rule matches all filters (if any)
        severity_match = not severities or rule['severity'] in severities
        name_match = not rule_names or test_name in rule_names
        type_match = not rule_types or rule['type'] in rule_types
        
        if severity_match and name_match and type_match:
            filtered_rules[test_name] = rule
    
    if rule_names and len(filtered_rules) < len(rule_names):
        # Find which requested rules don't exist
        missing_rules = set(rule_names) - set(filtered_rules.keys())
        print(f"\n{YELLOW}Warning: The following requested rules were not found: {', '.join(missing_rules)}{RESET}")
    
    total_filtered = len(filtered_rules)
    if total_filtered == 0:
        print(f"\n{YELLOW}Warning: No rules matched the specified criteria{RESET}")
        return results
        
    for i, (test_name, rule) in enumerate(filtered_rules.items(), 1):
        # Show test header first (unless in fail_only mode where we show it only if test fails)
        show_header = not fail_only
        if show_header:
            print(f"\n{'='*80}")
            print(f"Running test [{i}/{total_filtered}]: {test_name}")
            print(f"Type: {rule['type']} | Severity: {rule['severity']}")
            print(f"{'='*80}")
            print(f"  Running up to {iterations} iterations...")
        
        # Run the test
        result = run_single_test(target_client, target_model, target_model_type, 
                                 controller_client, controller_model, controller_model_type, 
                                 system_prompt, test_name, rule, iterations, firewall_mode, pass_condition, fail_only)
        
        # For fail_only mode, show header only if test failed
        if fail_only and not result["passed"]:
            print(f"\n{'='*80}")
            print(f"Running test [{i}/{total_filtered}]: {test_name}")
            print(f"Type: {rule['type']} | Severity: {rule['severity']}")
            print(f"{'='*80}")
        
        # Print summary (conditionally based on fail_only flag)
        if not fail_only or not result["passed"]:
            print(f"\n  --- Test Summary ---")
            if result["passed"]:
                passed_results_count += 1
                print(f"  Final Result: {GREEN}PASS{RESET} ({result['pass_rate']} passed)")
            else:
                if result.get("failed_result", {}).get("reason", "").startswith("API Error:"):
                    print(f"  Final Result: {YELLOW}ERROR{RESET} ({result['pass_rate']} passed)")
                    # Stop testing if we get an API error
                    print("\nStopping tests due to API error.")
                    results[test_name] = result
                    return results
                else:
                    print(f"  Final Result: {RED}FAIL{RESET} ({result['pass_rate']} passed)")
        
        results[test_name] = result
        
    print(f"\n================================================================================")
    print(f"Overall Summary")
    print(f"  Total Tests: {len(results)}")
    print(f"  Passed Tests: {passed_results_count}")
    print(f"  Failed Tests: {len(results) - passed_results_count}")
    print(f"================================================================================")

    print("\nAll tests completed.")
    return results
