"""Tests for model registry and configuration."""

import pytest
from unittest.mock import patch

from models import ModelRegistry, get_model_config, validate_model_availability


def test_model_registry_structure():
    """Test that model registry has correct structure."""
    registry = ModelRegistry()
    
    # Check required models exist
    assert "claude-opus-4-6" in registry.models
    assert "claude-sonnet-4-6" in registry.models
    assert "grok-4-1-thinking" in registry.models
    assert "glm-5" in registry.models
    assert "kimi-k2.5" in registry.models
    
    # Check model configurations
    opus = registry.models["claude-opus-4-6"]
    assert opus["provider"] == "anthropic"
    assert opus["model_id"] == "claude-opus-4-6"
    assert opus["api_key_env"] == "ANTHROPIC_API_KEY"
    
    grok = registry.models["grok-4-1-thinking"]
    assert grok["provider"] == "openai_compat"
    assert grok["model_id"] == "grok-4-1-fast-reasoning"
    assert grok["base_url"] == "https://api.x.ai/v1"
    assert grok["api_key_env"] == "XAI_API_KEY"


def test_get_model_config():
    """Test getting model configuration."""
    config = get_model_config("claude-opus-4-6")
    assert config["provider"] == "anthropic"
    assert config["model_id"] == "claude-opus-4-6"
    
    config = get_model_config("glm-5")
    assert config["provider"] == "openai_compat"
    assert config["base_url"] == "https://api.z.ai/api/paas/v4/"
    
    # Test invalid model
    with pytest.raises(ValueError, match="Unknown model"):
        get_model_config("invalid-model")


def test_validate_model_availability():
    """Test model availability validation."""
    # Test with API keys set
    with patch.dict("os.environ", {
        "ANTHROPIC_API_KEY": "test-key",
        "XAI_API_KEY": "test-key",
        "ZAI_API_KEY": "test-key",
        "MOONSHOT_API_KEY": "test-key"
    }):
        assert validate_model_availability("claude-opus-4-6") is True
        assert validate_model_availability("grok-4-1-thinking") is True
        assert validate_model_availability("glm-5") is True
        assert validate_model_availability("kimi-k2.5") is True
    
    # Test with missing API key
    with patch.dict("os.environ", {}, clear=True):
        assert validate_model_availability("claude-opus-4-6") is False


def test_model_role_mapping():
    """Test that models are mapped to correct roles."""
    registry = ModelRegistry()
    
    # Portfolio Manager should use Opus 4.6
    pm_model = registry.get_model_for_role("portfolio_manager")
    assert pm_model == "claude-opus-4-6"
    
    # Devil's Advocate should use Sonnet 4.6
    da_model = registry.get_model_for_role("devil_advocate")
    assert da_model == "claude-sonnet-4-6"
    
    # Research agents
    quant_model = registry.get_model_for_role("quant_researcher")
    assert quant_model == "grok-4-1-thinking"
    
    sentiment_model = registry.get_model_for_role("sentiment_researcher")
    assert sentiment_model == "glm-5"
    
    technical_model = registry.get_model_for_role("technical_researcher")
    assert technical_model == "kimi-k2.5"