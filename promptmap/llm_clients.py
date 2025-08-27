import os
import openai
from openai import OpenAI
import anthropic
from ollama import Client as OllamaClient
try:
    from google import genai
except ImportError:
    genai = None

from . import ollama_manager

def validate_api_keys(target_model_type: str, controller_model_type: str = None):
    """Validate that required API keys are present."""
    model_types = [target_model_type]
    if controller_model_type and controller_model_type != target_model_type:
        model_types.append(controller_model_type)
    
    for model_type in model_types:
        if model_type == "openai" and not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI models")
        elif model_type == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY environment variable is required for Anthropic models")
        elif model_type == "google" and not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY environment variable is required for Google models")
        elif model_type == "xai" and not os.getenv("XAI_API_KEY"):
            raise ValueError("XAI_API_KEY environment variable is required for XAI models")

def initialize_client(model_type: str, ollama_url: str = "http://localhost:11434"):
    """Initialize the appropriate client based on the model type."""
    if model_type == "openai":
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url="https://g-stg.ubitus.ai/v1")
    elif model_type == "anthropic":
        return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    elif model_type == "google":
        if genai is None:
            raise ImportError("google-genai package is required for Google models. Install with: pip install google-genai")
        return genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    elif model_type == "ollama":
        if not ollama_manager.is_ollama_running(ollama_url):
            if not ollama_manager.start_ollama(ollama_url):
                raise RuntimeError("Failed to start Ollama server")
        # Return Ollama client with custom URL
        return OllamaClient(host=ollama_url)
    elif model_type == "xai":
        return OpenAI(
            api_key=os.getenv("XAI_API_KEY"),
            base_url="https://api.x.ai/v1"
        )
    else:
        raise ValueError(f"Unsupported model type: {model_type}")

def initialize_clients(target_model_type: str, controller_model_type: str = None, ollama_url: str = "http://localhost:11434"):
    """Initialize target and controller clients."""
    target_client = initialize_client(target_model_type, ollama_url)
    
    if controller_model_type and controller_model_type != target_model_type:
        controller_client = initialize_client(controller_model_type, ollama_url)
    else:
        controller_client = target_client
    
    return target_client, controller_client


def test_prompt(client, model: str, model_type: str, system_prompt: str, test_prompt: str) -> tuple[str, bool]:
    """Send a test prompt to the LLM and get the response.
    Returns (response, is_error)"""
    try:
        if model_type == "openai":
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": test_prompt}
                ]
            )
            return response.choices[0].message.content, False
            
        elif model_type == "anthropic":
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": test_prompt
                    }
                ],
                system=system_prompt
            )
            return response.content[0].text, False
            
        elif model_type == "google":
            # For Google models, we need to combine system prompt and user prompt
            combined_prompt = f"System: {system_prompt}\n\nUser: {test_prompt}"
            response = client.models.generate_content(
                model=model,
                contents=combined_prompt
            )
            return response.text, False
            
        elif model_type == "ollama":
            ollama_manager.ensure_model_exists(model, client)
            response = client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": test_prompt}
                ]
            )
            return response['message']['content'], False
            
        elif model_type == "xai":
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": test_prompt}
                ]
            )
            return response.choices[0].message.content, False
            
    except Exception as e:
        return f"Error: {str(e)}", True