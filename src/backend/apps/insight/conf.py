"""LLM defaults (overridable via GlobalConfig)."""

CONFIG_KEY_LLM_PROVIDER = "insight.llm.provider"
CONFIG_KEY_LLM_OUTPUT_LANGUAGE = "insight.llm.output_language"
CONFIG_KEY_OPENAI_MODEL = "insight.llm.openai.model"
CONFIG_KEY_OPENAI_MAX_TOKENS = "insight.llm.openai.max_tokens"
CONFIG_KEY_OPENAI_TEMPERATURE = "insight.llm.openai.temperature"
CONFIG_KEY_AZURE_DEPLOYMENT = "insight.llm.azure.deployment"
CONFIG_KEY_AZURE_MAX_TOKENS = "insight.llm.azure.max_tokens"
CONFIG_KEY_AZURE_TEMPERATURE = "insight.llm.azure.temperature"
CONFIG_KEY_AZURE_API_VERSION = "insight.llm.azure.api_version"
CONFIG_KEY_GEMINI_MODEL = "insight.llm.gemini.model"
CONFIG_KEY_GEMINI_MAX_TOKENS = "insight.llm.gemini.max_tokens"
CONFIG_KEY_GEMINI_TEMPERATURE = "insight.llm.gemini.temperature"

DEFAULT_LLM_PROVIDER = "azure_openai"
DEFAULT_LLM_OUTPUT_LANGUAGE = "English"
DEFAULT_OPENAI_MODEL = "gpt-5-nano"
DEFAULT_OPENAI_MAX_TOKENS = 60000
DEFAULT_OPENAI_TEMPERATURE = 1.0
DEFAULT_AZURE_DEPLOYMENT = "gpt-5-nano"
DEFAULT_AZURE_API_VERSION = "2024-10-01-preview"
DEFAULT_AZURE_MAX_TOKENS = 60000
DEFAULT_AZURE_TEMPERATURE = 1.0
DEFAULT_GEMINI_MODEL = "gemini-1.5-pro"
DEFAULT_GEMINI_MAX_TOKENS = 60000
DEFAULT_GEMINI_TEMPERATURE = 0.7

# Langfuse tracing (overridable via GlobalConfig)
CONFIG_KEY_LANGFUSE_ENABLED = "observability.langfuse.enabled"
CONFIG_KEY_LANGFUSE_SAMPLE_RATE = "observability.langfuse.sample_rate"
CONFIG_KEY_LANGFUSE_TIMEOUT = "observability.langfuse.timeout_seconds"

DEFAULT_LANGFUSE_SAMPLE_RATE = 1.0
DEFAULT_LANGFUSE_TIMEOUT_SECONDS = 10
