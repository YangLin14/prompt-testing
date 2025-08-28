import argparse
import json
from dotenv import load_dotenv

from . import ollama_manager
from . import llm_clients
from .test_runner import run_tests
from .utils import redirect_stdout
from .constants import RED, RESET
from .improver import run_improver

load_dotenv()

def validate_model(model: str, model_type: str, auto_yes: bool = False, ollama_url: str = "http://localhost:11434") -> bool:
    """Validate if the model exists for the given model type."""
    if model_type == "ollama":
        if not ollama_manager.is_ollama_running(ollama_url):
            if not ollama_manager.start_ollama(ollama_url):
                print("Error: Could not start Ollama server")
                return False

        available_models = ollama_manager.get_available_ollama_models(ollama_url)
        if model not in available_models:
            print(f"Model '{model}' not found in Ollama.")
            # Show available models without duplicates
            unique_models = sorted(set(m.split(":")[0] for m in available_models))
            print("Available models:", ", ".join(unique_models) if unique_models else "No models found")
            
            if auto_yes:
                print(f"\nAutomatically downloading {model}...")
                return ollama_manager.download_ollama_model(model)
            
            response = input(f"\nWould you like to download {model}? [y/N] ").lower().strip()
            if response == 'y' or response == 'yes':
                print(f"\nDownloading {model}...")
                return ollama_manager.download_ollama_model(model)
            else:
                print("Download cancelled")
                return False
            
    return True

def show_help():
    """Show help message with usage examples."""
    print("""
Usage Examples:
-------------
1. Test with OpenAI (same model for target, controller, and improver):
   python -m promptmap.main --target-model-type openai --target-model llama-3.1-70b --improve

2. Test with Anthropic:
   python -m promptmap.main --target-model claude-3-opus-20240229 --target-model-type anthropic

3. Test with Google Gemini:
   python -m promptmap.main --target-model gemini-2.5-flash --target-model-type google

4. Test with Ollama (local):
   python -m promptmap.main --target-model llama2 --target-model-type ollama

   Test with Ollama (custom URL):
   python -m promptmap.main --target-model llama2 --target-model-type ollama --ollama-url http://192.168.1.100:11434

5. Test with XAI Grok:
   python -m promptmap.main --target-model grok-beta --target-model-type xai

6. Test with different target and controller models:
   python -m promptmap.main --target-model llama2 --target-model-type ollama --controller-model gpt-4 --controller-model-type openai

7. Test with different target, controller, and improver models:
   python -m promptmap.main --target-model-type openai --target-model llama-3.1-70b --controller-model llama-4-maverick-fp8 --controller-model-type openai --improve --improver-model llama-4-maverick-fp8 --improver-model-type openai

8. Run specific rules:
   python -m promptmap.main --target-model gpt-4 --target-model-type openai --rules harmful_hidden_recording,distraction_basic

9. Run specific rule types:
   python -m promptmap.main --target-model gpt-4 --target-model-type openai --rule-type distraction,hate
   # Available types: distraction, prompt_stealing, hate, social_bias, harmful, jailbreak, override

10. Custom options:
   python -m promptmap.main --target-model gpt-4 --target-model-type openai --iterations 3 --output results_gpt4.json

11. Firewall testing mode:
   python -m promptmap.main --target-model gpt-4 --target-model-type openai --firewall --pass-condition="true"
   # In firewall mode, tests pass only if the response contains the specified string
   # and is not more than twice its length

12. Show only failed tests (hide passed tests):
   python -m promptmap.main --target-model gpt-4 --target-model-type openai --fail

13. Save console output to a log file:
    python -m promptmap.main --target-model gpt-4 --target-model-type openai --log-file output.log

Note: Make sure to set the appropriate API key in your environment:
- For OpenAI models: export OPENAI_API_KEY="your-key"
- For Anthropic models: export ANTHROPIC_API_KEY="your-key"  
- For Google models: export GOOGLE_API_KEY="your-key"
- For XAI models: export XAI_API_KEY="your-key"

""")

def main():
    print(r'''
                              _________       __O     __O o_.-._ 
  Humans, Do Not Resist!  \|/   ,-'-.____()  / /\_,  / /\_|_.-._|
    _____   /            --O-- (____.--""" ___/\   ___/\  |      
   ( o.o ) /  Utku Sen's  /|\  -'--'_          /_      /__|_     
    | - | / _ __ _ _ ___ _ __  _ __| |_ _ __  __ _ _ __|___ \    
  /|     | | '_ \ '_/ _ \ '  \| '_ \  _| '  \/ _` | '_ \ __) |   
 / |     | | .__/_| \___/_|_|_| .__/\__|_|_|_\__,_| .__// __/    
/  |-----| |_|                |_|                 |_|  |_____|    
''')
    parser = argparse.ArgumentParser(description="Test LLM system prompts against injection attacks")
    parser.add_argument("--prompts", default="system-prompts.txt", help="Path to system prompts file")
    
    # Target model arguments (required)
    parser.add_argument("--target-model", required=True, help="Target LLM model name (model to be tested)")
    parser.add_argument("--target-model-type", required=True, choices=["openai", "anthropic", "google", "ollama", "xai"], 
                       help="Type of the target model (openai, anthropic, google, ollama, xai)")
    
    # Controller model arguments (optional - defaults to target model)
    parser.add_argument("--controller-model", help="Controller LLM model name (model for evaluation, defaults to target model)")
    parser.add_argument("--controller-model-type", choices=["openai", "anthropic", "google", "ollama", "xai"], 
                       help="Type of the controller model (openai, anthropic, google, ollama, xai, defaults to target model type)")
    parser.add_argument("--improve", action="store_true", help="Run the improver to suggest a better system prompt after tests complete.")
    parser.add_argument("--improver-model", help="LLM model to use for the improvement suggestion (defaults to controller model).")
    parser.add_argument("--improver-model-type", choices=["openai", "anthropic", "google", "ollama", "xai"], help="Type of the improver model (defaults to controller model type).")
    parser.add_argument("--severity", type=lambda s: [item.strip() for item in s.split(',')],
                       default=["low", "medium", "high"],
                       help="Comma-separated list of severity levels (low,medium,high). Defaults to all severities.")
    parser.add_argument("--rules", type=lambda s: [item.strip() for item in s.split(',')],
                       help="Comma-separated list of rule names to run. If not specified, all rules will be run.")
    parser.add_argument("--rule-type", type=lambda s: [item.strip() for item in s.split(',')],
                       default=["all"],
                       help="Comma-separated list of rule types to run (distraction,prompt_stealing,hate,social_bias,harmful,jailbreak, override). Default: all")
    parser.add_argument("--output", default="results.json", help="Output file for results")
    parser.add_argument("-y", "--yes", action="store_true", help="Automatically answer yes to all prompts")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations to run for each test")
    parser.add_argument("--firewall", action="store_true", help="Enable firewall testing mode")
    parser.add_argument("--pass-condition", help="Expected response in firewall mode (required if --firewall is used)")
    parser.add_argument("--fail", action="store_true", help="Only print failed test cases (hide passed cases)")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama server URL (default: http://localhost:11434)")
    parser.add_argument("--log-file", default="output.log", help="Redirect all console output to a specified file.")
    
    args = parser.parse_args()

    def run_application():
        try:
            # Set controller model defaults
            if not args.controller_model:
                args.controller_model = args.target_model
            if not args.controller_model_type:
                args.controller_model_type = args.target_model_type
            
            # Validate severity levels
            valid_severities = {"low", "medium", "high"}
            if args.severity:
                invalid_severities = [s for s in args.severity if s not in valid_severities]
                if invalid_severities:
                    raise ValueError(f"Invalid severity level(s): {', '.join(invalid_severities)}. Valid levels are: low, medium, high")
            
            # Validate and process rule types
            valid_rule_types = {"distraction", "prompt_stealing", "hate", "social_bias", "harmful", "jailbreak", "override"}
            if args.rule_type == ["all"]:
                rule_types = None  # None means all types
            else:
                rule_types = args.rule_type
                invalid_types = [t for t in rule_types if t not in valid_rule_types]
                if invalid_types:
                    raise ValueError(f"Invalid rule type(s): {', '.join(invalid_types)}. Valid types is: distraction, prompt_stealing, hate, social_bias, harmful, jailbreak, override")
            
            # Validate firewall mode arguments
            if args.firewall and not args.pass_condition:
                raise ValueError("--pass-condition is required when using --firewall mode")
            
            # Validate models before running tests
            if not validate_model(args.target_model, args.target_model_type, args.yes, args.ollama_url):
                return 1
            
            # Only validate controller model if it's different from target
            if (args.controller_model != args.target_model or args.controller_model_type != args.target_model_type):
                if not validate_model(args.controller_model, args.controller_model_type, args.yes, args.ollama_url):
                    return 1
            
            llm_clients.validate_api_keys(args.target_model_type, args.controller_model_type)
            results = run_tests(args.target_model, args.target_model_type, args.controller_model, args.controller_model_type, 
                              args.prompts, args.iterations, args.severity, args.rules, rule_types, args.firewall, args.pass_condition, args.fail, args.ollama_url)
            
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            if args.improve:
                # Determine which model and client to use for the improver
                improver_model = args.improver_model or args.controller_model
                improver_model_type = args.improver_model_type or args.controller_model_type
                
                print(f"\nInitializing client for Improver LLM: {improver_model} ({improver_model_type})")
                llm_clients.validate_api_keys(improver_model_type)
                improver_client = llm_clients.initialize_client(improver_model_type, args.ollama_url)

                run_improver(
                    client=improver_client,
                    model=improver_model,
                    model_type=improver_model_type,
                    original_prompt_path=args.prompts,
                    results_path=args.output
                )
                
        except ValueError as e:
            print(f"\n{RED}Error:{RESET} {str(e)}")
            show_help()
            return 1
        except Exception as e:
            print(f"\n{RED}Error:{RESET} An unexpected error occurred: {str(e)}")
            show_help()
            return 1
            
        return 0

    if args.log_file:
        # If a log file is specified, run the application with stdout redirected.
        # A message is printed to the console first to let the user know.
        print(f"Redirecting all output to '{args.log_file}'. Check this file for progress.")
        with open(args.log_file, 'w', encoding='utf-8', buffering=1) as log_f:
            with redirect_stdout(log_f):
                return run_application()
    else:
        # Otherwise, run the application normally, printing to the console.
        return run_application()

if __name__ == "__main__":
    main()