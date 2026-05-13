"""Chat template engine (Jinja2) + proper tokenizer with tiktoken fallback."""

from typing import Optional

# ── Chat Template Engine ───────────────────────────────────────


class ChatTemplate:
    """Renders chat messages using model-specific Jinja2-like templates."""

    _TEMPLATES = {
        "llama3": {
            "system": "<|start_header_id|>system<|end_header_id|>\n\n{content}<|eot_id|>",
            "user": "<|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|>",
            "assistant": "<|start_header_id|>assistant<|end_header_id|>\n\n{content}<|eot_id|>",
            "tool": "<|start_header_id|>tool<|end_header_id|>\n\n{content}<|eot_id|>",
        },
        "mistral": {
            "system": "<s>[INST] {content} [/INST]",
            "user": "<s>[INST] {content} [/INST]",
            "assistant": "{content}</s>",
            "tool": "<s>[TOOL_RESULTS] {content} [/TOOL_RESULTS]",
        },
        "chatml": {
            "system": "<|im_start|>system\n{content}<|im_end|>\n",
            "user": "<|im_start|>user\n{content}<|im_end|>\n",
            "assistant": "<|im_start|>assistant\n{content}<|im_end|>\n",
            "tool": "<|im_start|>tool\n{content}<|im_end|>\n",
        },
        "zephyr": {
            "system": "<|system|>\n{content}</s>\n",
            "user": "<|user|>\n{content}</s>\n",
            "assistant": "<|assistant|>\n{content}</s>\n",
            "tool": "<|tool|>\n{content}</s>\n",
        },
        "gemma": {
            "system": "<bos><start_of_turn>system\n{content}<end_of_turn>\n",
            "user": "<start_of_turn>user\n{content}<end_of_turn>\n",
            "assistant": "<start_of_turn>model\n{content}<end_of_turn>\n",
            "tool": "<start_of_turn>tool\n{content}<end_of_turn>\n",
        },
        "legacy": {
            "system": "System: {content}\n\n",
            "user": "Human: {content}\n\n",
            "assistant": "Assistant: {content}\n\n",
            "tool": "Tool result (call_id={tool_call_id}): {content}\n\n",
        },
    }

    _DETECTION_MAP = {
        "llama-3": "llama3",
        "llama3": "llama3",
        "mistral": "mistral",
        "mixtral": "mistral",
        "gemma": "gemma",
        "zephyr": "zephyr",
        "phi": "chatml",
        "openchat": "chatml",
        "neural": "chatml",
        "tinyllama": "tinyllama",
        "tiny-llama": "tinyllama",
    }

    _TEMPLATES["tinyllama"] = {
        "system": "<|system|>\n{content}</s>\n",
        "user": "<|user|>\n{content}</s>\n",
        "assistant": "<|assistant|>\n{content}</s>\n",
        "tool": "<|tool|>\n{content}</s>\n",
    }

    @classmethod
    def detect_template(cls, model_name: str) -> str:
        model_lower = model_name.lower()
        for keyword, template_name in cls._DETECTION_MAP.items():
            if keyword in model_lower:
                return template_name
        return "legacy"

    @classmethod
    def render_messages(
        cls,
        messages: list[dict],
        model_name: str = "",
        add_generation_prompt: bool = True,
    ) -> str:
        template_name = cls.detect_template(model_name)
        templates = cls._TEMPLATES.get(template_name, cls._TEMPLATES["legacy"])
        parts: list[str] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, list):
                text_parts = [
                    p.get("text", "")
                    for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                content = " ".join(text_parts) if text_parts else ""

            tpl = templates.get(role, "{content}")
            formatted = tpl.format(
                content=content,
                tool_call_id=msg.get("tool_call_id", ""),
            )

            if role == "user" and template_name == "llama3":
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    import json

                    formatted = formatted.replace(
                        "<|eot_id|>",
                        "<|start_header_id|>tool_calls<|end_header_id|>\n\n"
                        + json.dumps(tool_calls)
                        + "<|eot_id|>",
                    )

            parts.append(formatted)

        if add_generation_prompt:
            if template_name == "llama3":
                parts.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
            elif template_name == "chatml":
                parts.append("<|im_start|>assistant\n")
            elif template_name == "legacy":
                parts.append("Assistant:\n")

        return "".join(parts)

    @classmethod
    def list_templates(cls) -> list[str]:
        return list(cls._TEMPLATES.keys())

    @classmethod
    def register_template(cls, name: str, templates: dict[str, str]) -> None:
        cls._TEMPLATES[name] = templates


chat_template = ChatTemplate()


# ── Proper Tokenizer ───────────────────────────────────────────


class Tokenizer:
    """Model-aware tokenizer with tiktoken/sentencepiece fallback."""

    _tiktoken_models: Optional[dict] = None

    @classmethod
    def _get_tiktoken(cls):
        if cls._tiktoken_models is None:
            try:
                import tiktoken

                cls._tiktoken_models = {
                    "gpt-4": tiktoken.encoding_for_model("gpt-4"),
                    "gpt-3.5": tiktoken.encoding_for_model("gpt-3.5-turbo"),
                    "cl100k": tiktoken.get_encoding("cl100k_base"),
                }
            except ImportError:
                cls._tiktoken_models = {}
        return cls._tiktoken_models

    @classmethod
    def count(cls, text: str, model: str = "") -> int:
        tt = cls._get_tiktoken()

        # Try tiktoken for known models
        if tt:
            if "gpt-4" in model.lower():
                return len(tt["gpt-4"].encode(text))
            if "gpt-3" in model.lower() or "turbo" in model.lower():
                return len(tt["gpt-3.5"].encode(text))
            if model:
                for enc_name, enc in tt.items():
                    try:
                        return len(enc.encode(text))
                    except Exception:
                        pass

        # Try sentencepiece for LLaMA models
        try:
            import sentencepiece as spm

            if hasattr(spm, "SentencePieceProcessor"):
                pass  # would load model-specific spm model
        except ImportError:
            pass

        # Heuristic fallback (word count * 1.3 + char count * 0.25)
        words = len(text.split())
        chars = len(text)
        punct = sum(1 for c in text if c in ".,!?;:\"'()[]{}")
        return max(1, int(words * 1.3 + chars * 0.25 + punct * 0.1))

    @classmethod
    def count_messages(cls, messages: list[dict], model: str = "") -> int:
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    p.get("text", "")
                    for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                )
            total += cls.count(str(content), model)
        # Add overhead for message formatting (~4 tokens per message)
        total += len(messages) * 4
        return total


tokenizer = Tokenizer()
