import os
import requests
import subprocess
import time
from typing import List

def is_ollama_running(ollama_url: str = "http://localhost:11434") -> bool:
    """Check if Ollama server is running."""
    try:
        requests.get(f"{ollama_url}/api/tags")
        return True
    except requests.exceptions.ConnectionError:
        return False

def get_ollama_path():
    """Get the path to ollama executable."""
    common_paths = [
        "/usr/local/bin/ollama",  # Default macOS install location
        "/opt/homebrew/bin/ollama",  # M1 Mac Homebrew location
        "ollama"  # If it's in PATH
    ]
    
    for path in common_paths:
        if os.path.exists(path) or os.system(f"which {path} > /dev/null 2>&1") == 0:
            return path
    
    raise FileNotFoundError("Ollama executable not found. Please make sure Ollama is installed.")

def start_ollama(ollama_url: str = "http://localhost:11434"):
    """Start Ollama server."""
    print("Connecting to the Ollama server...")
    try:
        ollama_path = get_ollama_path()
        subprocess.Popen([ollama_path, "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Wait for server to start
        for _ in range(10):
            if is_ollama_running(ollama_url):
                print("Ollama server is running")
                return True
            time.sleep(1)
        return False
    except FileNotFoundError as e:
        print(e)
        print("Please install Ollama first: https://ollama.ai/download")
        return False

def download_ollama_model(model: str) -> bool:
    """Download an Ollama model."""
    try:
        ollama_path = get_ollama_path()
        # Run the command and let it inherit the parent's stdout/stderr directly
        result = subprocess.run([ollama_path, "pull", model], check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"\n{RED}Error downloading model: {str(e)}{RESET}")
        return False

def get_available_ollama_models(ollama_url: str = "http://localhost:11434") -> List[str]:
    """Get list of available Ollama models."""
    try:
        response = requests.get(f"{ollama_url}/api/tags")
        if response.status_code == 200:
            models = response.json().get("models", [])
            # Return both full names and base names without tags
            model_names = []
            for model in models:
                name = model["name"]
                model_names.append(name)
                # Add base name without tag
                if ":" in name:
                    model_names.append(name.split(":")[0])
            return model_names
        return []
    except:
        return []

def ensure_model_exists(model: str, ollama_client):
    """Ensure the Ollama model exists, download if not."""
    try:
        ollama_client.list()
    except Exception:
        print(f"Model {model} not found. Downloading...")
        try:
            ollama_client.pull(model)
            print(f"Model {model} downloaded successfully")
        except Exception as e:
            print(f"Error downloading model: {str(e)}")
            raise