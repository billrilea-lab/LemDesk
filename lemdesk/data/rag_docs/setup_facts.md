# Docker AI setup facts (extracted)

```json
{
  "extracted_at": "2026-06-21T22:36:53.929146+00:00",
  "ports": [
    "12434"
  ],
  "base_urls": [],
  "env_vars": [
    "GORDON_BASE_URL"
  ],
  "models": [
    "ai/all-minilm",
    "ai/devstral-small-2",
    "ai/glm-4.7-flash",
    "ai/llama3.2",
    "ai/qwen2.5-coder",
    "ai/qwen3",
    "ai/qwen3-coder",
    "ai/smollm2"
  ],
  "cli_commands_sample": [],
  "sbx_commands_sample": [],
  "cursor_integration": {
    "openai_api_key": "not-needed",
    "override_openai_base_url_local": "http://localhost:12434/engines/v1",
    "override_openai_base_url_lan": "http://<server-ip>:12434/engines/v1",
    "anthropic_base_url_local": "http://localhost:12434",
    "model_id_examples": [
      "ai/devstral-small-2",
      "ai/glm-4.7-flash",
      "ai/llama3.2",
      "ai/qwen2.5-coder",
      "ai/qwen3-coder",
      "ai/smollm2"
    ],
    "notes": [
      "Use full model name with ai/ prefix",
      "Enable host-side TCP in Docker Desktop Settings > AI",
      "Add CORS origins for browser-based tools"
    ]
  },
  "dmr_defaults": {
    "tcp_port": 12434,
    "openai_compatible_base": "http://localhost:12434/engines/v1",
    "ollama_compatible_base": "http://localhost:12434",
    "container_base": "http://model-runner.docker.internal"
  }
}
```
