"""Tests for agent call functions."""

import re
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from agents import (
    call_anthropic_agent,
    call_openai_compat_agent,
    call_agent,
    clean_thinking_tokens,
    RateLimiter
)


@pytest.mark.asyncio
async def test_call_anthropic_agent():
    """Test calling Anthropic models."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="This is a test response")]
    mock_client.messages.create.return_value = mock_response
    
    with patch("agents.anthropic.Anthropic", return_value=mock_client):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = await call_anthropic_agent(
                model_id="claude-opus-4-6",
                system_prompt="You are a test assistant",
                user_prompt="Test message"
            )
    
    assert result == "This is a test response"
    mock_client.messages.create.assert_called_once_with(
        model="claude-opus-4-6",
        max_tokens=2000,
        system="You are a test assistant",
        messages=[{"role": "user", "content": "Test message"}]
    )


@pytest.mark.asyncio
async def test_call_openai_compat_agent():
    """Test calling OpenAI-compatible models."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Test response from OpenAI"))]
    mock_client.chat.completions.create.return_value = mock_response
    
    with patch("agents.openai.OpenAI", return_value=mock_client):
        with patch.dict("os.environ", {"XAI_API_KEY": "test-key"}):
            result = await call_openai_compat_agent(
                model_id="grok-4-1-fast-reasoning",
                base_url="https://api.x.ai/v1",
                system_prompt="You are a test assistant",
                user_prompt="Test message",
                api_key_env="XAI_API_KEY"
            )
    
    assert result == "Test response from OpenAI"
    mock_client.chat.completions.create.assert_called_once()


def test_clean_thinking_tokens():
    """Test cleaning thinking tokens from model responses."""
    # Test with think tags
    text_with_think = """<think>
    This is internal reasoning that should be removed.
    Let me think about this problem...
    </think>
    This is the actual response that should remain."""
    
    cleaned = clean_thinking_tokens(text_with_think)
    assert "<think>" not in cleaned
    assert "internal reasoning" not in cleaned
    assert "This is the actual response that should remain." in cleaned
    
    # Test with nested think tags
    text_nested = """<think>First thought</think>
    Some content
    <think>Another thought</think>
    Final content"""
    
    cleaned = clean_thinking_tokens(text_nested)
    assert "<think>" not in cleaned
    assert "First thought" not in cleaned
    assert "Another thought" not in cleaned
    assert "Some content" in cleaned
    assert "Final content" in cleaned
    
    # Test with no thinking tokens
    normal_text = "This is a normal response without any thinking tokens."
    assert clean_thinking_tokens(normal_text) == normal_text


@pytest.mark.asyncio
async def test_call_agent_with_anthropic():
    """Test the unified agent call function with Anthropic."""
    with patch("agents.call_anthropic_agent", new_callable=AsyncMock) as mock_anthropic:
        mock_anthropic.return_value = "Anthropic response"
        
        result = await call_agent(
            model_key="claude-opus-4-6",
            system_prompt="Test system",
            user_prompt="Test user"
        )
        
        assert result == "Anthropic response"
        mock_anthropic.assert_called_once()


@pytest.mark.asyncio
async def test_call_agent_with_openai_compat():
    """Test the unified agent call function with OpenAI-compatible model."""
    with patch("agents.call_openai_compat_agent", new_callable=AsyncMock) as mock_openai:
        mock_openai.return_value = "<think>Internal thinking</think>Actual response"
        
        result = await call_agent(
            model_key="grok-4-1-thinking",
            system_prompt="Test system",
            user_prompt="Test user"
        )
        
        # Should clean thinking tokens for Grok model
        assert result == "Actual response"
        mock_openai.assert_called_once()


@pytest.mark.asyncio
async def test_call_agent_timeout():
    """Test agent call with timeout."""
    with patch("agents.call_anthropic_agent", new_callable=AsyncMock) as mock_anthropic:
        import asyncio
        
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)  # Simulate slow response
            return "Too slow"
        
        mock_anthropic.side_effect = slow_response
        
        with pytest.raises(asyncio.TimeoutError):
            await call_agent(
                model_key="claude-opus-4-6",
                system_prompt="Test",
                user_prompt="Test",
                timeout=0.1  # Very short timeout
            )


@pytest.mark.asyncio
async def test_rate_limiter():
    """Test rate limiting functionality."""
    rate_limiter = RateLimiter()
    
    # Test same provider calls
    start_time = pytest.approx(0, abs=0.5)
    
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await rate_limiter.wait_if_needed("anthropic")
        mock_sleep.assert_not_called()  # First call shouldn't wait
        
        await rate_limiter.wait_if_needed("anthropic")
        mock_sleep.assert_called_once()  # Second call to same provider should wait
        
        mock_sleep.reset_mock()
        await rate_limiter.wait_if_needed("openai_compat")
        mock_sleep.assert_not_called()  # Different provider shouldn't wait