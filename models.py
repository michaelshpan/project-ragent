"""Model registry and configuration for Investment Committee Agent Framework."""

import os
from typing import Dict, Any, Optional


class ModelRegistry:
    """Central registry for all LLM models and their configurations."""
    
    def __init__(self):
        self.models = {
            "claude-opus-4-6": {
                "provider": "anthropic",
                "model_id": "claude-opus-4-6",
                "display_name": "Claude Opus 4.6",
                "api_key_env": "ANTHROPIC_API_KEY"
            },
            "claude-sonnet-4-6": {
                "provider": "anthropic",
                "model_id": "claude-sonnet-4-6",
                "display_name": "Claude Sonnet 4.6",
                "api_key_env": "ANTHROPIC_API_KEY"
            },
            "grok-4-1-thinking": {
                "provider": "openai_compat",
                "model_id": "grok-4-1-fast-reasoning",
                "display_name": "Grok 4.1 (Thinking)",
                "base_url": "https://api.x.ai/v1",
                "api_key_env": "XAI_API_KEY",
                "is_thinking_model": True,
                "max_tokens": 8192
            },
            "glm-5": {
                "provider": "openai_compat",
                "model_id": "glm-5",
                "display_name": "GLM-5",
                "base_url": "https://api.z.ai/api/paas/v4/",
                "api_key_env": "ZAI_API_KEY"
            },
            "kimi-k2.5": {
                "provider": "openai_compat",
                "model_id": "kimi-k2.5",
                "display_name": "Kimi K2.5",
                "base_url": "https://api.moonshot.cn/v1",
                "api_key_env": "MOONSHOT_API_KEY",
                "is_thinking_model": True,
                "max_tokens": 8192
            }
        }
        
        # Map roles to models
        self.role_mapping = {
            "portfolio_manager": "claude-opus-4-6",
            "devil_advocate": "claude-sonnet-4-6",
            "quant_researcher": "grok-4-1-thinking",
            "sentiment_researcher": "glm-5",
            "technical_researcher": "kimi-k2.5"
        }
    
    def get_model_for_role(self, role: str) -> str:
        """Get the model key for a specific role."""
        if role not in self.role_mapping:
            raise ValueError(f"Unknown role: {role}")
        return self.role_mapping[role]
    
    def get_config(self, model_key: str) -> Dict[str, Any]:
        """Get configuration for a specific model."""
        if model_key not in self.models:
            raise ValueError(f"Unknown model: {model_key}")
        return self.models[model_key]
    
    def validate_availability(self, model_key: str) -> bool:
        """Check if a model's API key is available."""
        config = self.get_config(model_key)
        api_key = os.environ.get(config["api_key_env"], "")
        return bool(api_key)
    
    def get_available_models(self) -> list:
        """Return list of models with availability status."""
        return [
            {
                "id": key,
                "display_name": config["display_name"],
                "provider": config["provider"],
                "available": self.validate_availability(key)
            }
            for key, config in self.models.items()
        ]


# Singleton instance
_registry = ModelRegistry()


def get_model_config(model_key: str) -> Dict[str, Any]:
    """Get configuration for a specific model."""
    return _registry.get_config(model_key)


def validate_model_availability(model_key: str) -> bool:
    """Check if a model's API key is available."""
    return _registry.validate_availability(model_key)


def get_model_for_role(role: str) -> str:
    """Get the model key for a specific role."""
    return _registry.get_model_for_role(role)


def get_all_required_models() -> list:
    """Get list of all models required for the pipeline."""
    return list(_registry.role_mapping.values())


def check_all_models_available() -> tuple[bool, list]:
    """Check if all required models have API keys available."""
    missing = []
    for model_key in get_all_required_models():
        if not validate_model_availability(model_key):
            config = get_model_config(model_key)
            missing.append({
                "model": model_key,
                "display_name": config["display_name"],
                "env_var": config["api_key_env"]
            })
    
    return len(missing) == 0, missing