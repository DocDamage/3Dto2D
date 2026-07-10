# Local Forge Guide

Forge is SpriteForge's project-aware companion. It explains setup, creation,
review, repair, and export using approved local documentation and safe project
context.

## Default behavior

The guide works without a language model. Its deterministic retrieval mode:

- reads only an explicit allowlist of bundled SpriteForge guides and presets;
- accepts bounded, filtered context from the current local project;
- returns plain-language answers with local source labels;
- suggests navigation only; and
- cannot run commands, start jobs, delete files, or change project data.

This mode is enabled by default and has no model download or external network
requirement.

## Optional small local model

A small local model can rewrite retrieved facts into more natural answers. The
model is optional and disabled by default. SpriteForge never downloads or starts
one automatically.

Recommended starting points for Ollama:

```powershell
ollama run qwen3:1.7b
```

`qwen3:1.7b` is the balanced default suggestion. `gemma3:1b` uses less storage
and memory; `phi4-mini` is larger and often gives stronger explanations.

After the model is available, open **Settings → Playful workshop → Optional
embedded language model**, enable the model, keep the endpoint at
`http://127.0.0.1:11434`, enter the model name, and save.

SpriteForge also supports an OpenAI-compatible server running on the same
computer. Model endpoints must resolve to `localhost` or a loopback IP address.
Remote endpoints are rejected.

## Environment configuration

The same values can be supplied without editing the JSON config:

```text
SPRITEFORGE_ASSISTANT_LLM_ENABLED=true
SPRITEFORGE_ASSISTANT_PROVIDER=ollama
SPRITEFORGE_ASSISTANT_ENDPOINT=http://127.0.0.1:11434
SPRITEFORGE_ASSISTANT_MODEL=qwen3:1.7b
```

Supported providers are `ollama` and `openai_compatible`.

## Safety boundaries

- Retrieved text and model output are treated as untrusted content.
- Model answers cannot create executable UI actions.
- Only allowlisted navigation destinations are returned to the browser.
- Secret-looking configuration keys and values are removed from retrieval.
- Requests and responses have strict size and time limits.
- The API is protected by SpriteForge's session token and rate limiter.
- If the local model fails or returns unsafe instructions, the deterministic
  answer remains available.

## API

`GET /api/assistant/status` returns retrieval/model readiness.

`POST /api/assistant/query` accepts:

```json
{
  "question": "What should I do next?",
  "project": "DemoProject",
  "view": "guide",
  "context": {
    "job_running": false,
    "generation_ready": true,
    "output_count": 1
  }
}
```

`POST /api/assistant/settings` saves only the bounded local-model settings. It
does not accept remote endpoints or expose stored API keys.

Official references:

- [Ollama API](https://docs.ollama.com/api/chat)
- [Qwen3 1.7B](https://huggingface.co/Qwen/Qwen3-1.7B)
- [Gemma 3](https://ollama.com/library/gemma3)
- [Phi-4 Mini](https://huggingface.co/microsoft/Phi-4-mini-instruct)
