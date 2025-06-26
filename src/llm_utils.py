import g4f
import ssl
import time
from config import get_model, get_verbose
from constants import parse_model
from status import info, warning, error

def get_available_providers():
    """
    Get a list of available working providers from g4f.
    Filters out providers that are known to be problematic.
    
    Returns:
        List of available provider classes
    """
    # Get all provider classes that are marked as working
    providers = []
    
    # Known working providers to try first
    priority_providers = [
        "You",
        "DeepAi",
        "Bing",
        "OpenaiChat",
        "DeepInfra",
        "Bard",
        "Gemini",
        "Liaobots"
    ]
    
    # Add priority providers first if they exist and are working
    for provider_name in priority_providers:
        if hasattr(g4f.Provider, provider_name):
            provider = getattr(g4f.Provider, provider_name)
            if hasattr(provider, 'working') and provider.working:
                providers.append(provider)
    
    # Add remaining working providers
    for provider in dir(g4f.Provider):
        if provider.startswith('__'):  # Skip internal attributes
            continue
        
        provider_class = getattr(g4f.Provider, provider)
        if (provider_class not in providers and  # Skip if already added
            hasattr(provider_class, 'working') and 
            provider_class.working and
            not provider_class.__name__.startswith('_')):
            providers.append(provider_class)
    
    if get_verbose():
        info(f" => Available providers: {[p.__name__ for p in providers]}")
    
    return providers

def generate_response(prompt: str, model: any = None, max_retries: int = 3) -> str:
    """
    Generates an LLM Response based on a prompt and the user-provided model.
    Includes retry logic and error handling.

    Args:
        prompt (str): The prompt to use in the text generation.
        model (any, optional): The specific model to use. If None, uses the default model from config.
        max_retries (int, optional): Maximum number of retry attempts. Defaults to 3.

    Returns:
        response (str): The generated AI Response.
    """
    if not model:
        model = parse_model(get_model())
    
    # Log input parameters if verbose mode is enabled
    if get_verbose():
        info(f" => LLM Request:")
        info(f"    Model: {model}")
        info(f"    Prompt: {prompt}\n")
    
    # Create an unverified SSL context
    ssl._create_default_https_context = ssl._create_unverified_context
    
    # Get list of available providers
    providers = get_available_providers()
    
    if not providers:
        error("No working providers found")
        return None
    
    for attempt in range(max_retries):
        for provider in providers:
            try:
                if get_verbose():
                    info(f" => Trying provider: {provider.__name__}")
                
                response = g4f.ChatCompletion.create(
                    model=model,
                    provider=provider,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }],
                    timeout=30
                )
                
                if response and len(response.strip()) > 0:
                    # Log response if verbose mode is enabled
                    if get_verbose():
                        info(f" => LLM Response from {provider.__name__}: {response}\n")
                    return response
                    
            except Exception as e:
                if get_verbose():
                    warning(f"Provider {provider.__name__} failed: {str(e)}")
                continue
                
        if attempt < max_retries - 1:
            if get_verbose():
                warning(f"All providers failed on attempt {attempt + 1}, retrying in 5 seconds...")
            time.sleep(5)
            # Refresh provider list in case some became available
            providers = get_available_providers()
    
    error("All LLM providers failed after maximum retries")
    return None 