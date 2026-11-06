"""Tests for TokenRateLimitPolicy"""

from mockserver.llm import Completion, Provider, Usage

MODEL = "meta-llama/Llama-3.1-8B-Instruct"

CHAT_MESSAGES = [{"role": "user", "content": "What is Kubernetes?"}]

STREAMING_REQUEST = {
    "model": MODEL,
    "messages": CHAT_MESSAGES,
    "stream": True,  # enable streaming
    "usage": True,  # ensures `usage.total_tokens` is returned in the response
    "stream_options": {"include_usage": True},
    "max_tokens": 15,
}

MOCK_INPUT_TOKENS = 5
MOCK_OUTPUT_TOKENS = 10
MOCK_TOTAL_TOKENS = MOCK_INPUT_TOKENS + MOCK_OUTPUT_TOKENS


def register_chat_completion_mock(mockserver_client):
    """Registers a fixed-usage, non-streaming OpenAI-shaped chat completion mock"""
    mockserver_client.create_llm_response_expectation(
        "trlp-chat-completion",
        "/v1/chat/completions",
        Provider.OPENAI,
        completion=Completion(
            text="mocked response", usage=Usage(input_tokens=MOCK_INPUT_TOKENS, output_tokens=MOCK_OUTPUT_TOKENS)
        ),
        model=MODEL,
    )


def register_streaming_chat_completion_mock(mockserver_client):
    """Registers a fixed-usage, streaming OpenAI-shaped chat completion mock"""
    mockserver_client.create_llm_response_expectation(
        "trlp-chat-completion-stream",
        "/v1/chat/completions",
        Provider.OPENAI,
        completion=Completion(
            text="mocked response",
            usage=Usage(input_tokens=MOCK_INPUT_TOKENS, output_tokens=MOCK_OUTPUT_TOKENS),
            streaming=True,
        ),
        model=MODEL,
    )
