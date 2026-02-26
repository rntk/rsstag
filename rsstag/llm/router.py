import inspect
import logging
from typing import Optional, Tuple, Dict, Any

from rsstag.llm.batch import LlmBatchProvider, NebiusBatchProvider, OpenAIBatchProvider


class LLMRouter:
    def __init__(self, config: dict) -> None:
        self._config = config
        self._handlers: Dict[str, Optional[Any]] = {}
        self._model_handlers: Dict[Tuple[str, str], Optional[Any]] = {}
        self._batch_providers: Dict[str, LlmBatchProvider] = {}
        self._init_handlers()
        self._init_batch_providers()

    def _init_handlers(self) -> None:
        for name in ("llamacpp", "openai", "anthropic", "groqcom", "cerebras"):
            self._handlers[name] = self._safe_build(name, None)

    def _init_batch_providers(self) -> None:
        openai_cfg = self._config.get("openai", {})
        if openai_cfg.get("token"):
            try:
                model = openai_cfg.get("batch_model") or openai_cfg.get("model")
                if not model:
                    openai_handler = self._handlers.get("openai")
                    model = getattr(openai_handler, "model", None) or "gpt-5-mini"
                self._batch_providers["openai"] = OpenAIBatchProvider(
                    openai_cfg["token"],
                    model,
                    batch_host=openai_cfg.get("batch_host"),
                )
            except Exception as e:
                logging.warning("Can't initialize OpenAI batch provider: %s", e)

        nebius_cfg = self._config.get("nebius", {})
        if nebius_cfg.get("token"):
            try:
                model = (
                    nebius_cfg.get("batch_model")
                    or nebius_cfg.get("model")
                    or "Qwen/Qwen3-235B-A22B"
                )
                self._batch_providers["nebius"] = NebiusBatchProvider(
                    nebius_cfg["token"],
                    model,
                    batch_host=nebius_cfg.get("batch_host"),
                )
            except Exception as e:
                logging.warning("Can't initialize Nebius batch provider: %s", e)

    def _safe_build(self, name: str, model: Optional[str]) -> Optional[Any]:
        try:
            return self._build_handler(name, model)
        except Exception as e:
            logging.warning("Can't initialize %s: %s", name, e)
            return None

    def _build_handler(self, name: str, model: Optional[str]) -> Any:
        if name == "llamacpp":
            from rsstag.llm.llamacpp import LLamaCPP

            if model:
                return LLamaCPP(self._config["llamacpp"]["host"], model=model)
            return LLamaCPP(self._config["llamacpp"]["host"])
        if name == "openai":
            from rsstag.llm.openai import ROpenAI

            if model:
                return ROpenAI(self._config["openai"]["token"], model=model)
            cfg_model = self._config["openai"].get("model")
            if cfg_model:
                return ROpenAI(self._config["openai"]["token"], model=cfg_model)
            return ROpenAI(self._config["openai"]["token"])
        if name == "anthropic":
            from rsstag.llm.anthropic import Anthropic

            if model:
                return Anthropic(self._config["anthropic"]["token"], model=model)
            return Anthropic(self._config["anthropic"]["token"])
        if name == "groqcom":
            from rsstag.llm.groqcom import GroqCom

            if model:
                return GroqCom(
                    host=self._config["groqcom"]["host"],
                    token=self._config["groqcom"]["token"],
                    model=model,
                )
            return GroqCom(
                host=self._config["groqcom"]["host"],
                token=self._config["groqcom"]["token"],
            )
        if name == "cerebras":
            from rsstag.llm.cerebras import RCerebras

            if model:
                return RCerebras(token=self._config["cerebras"]["token"], model=model)
            if self._config["cerebras"].get("model"):
                return RCerebras(
                    token=self._config["cerebras"]["token"],
                    model=self._config["cerebras"]["model"],
                )
            return RCerebras(token=self._config["cerebras"]["token"])
        raise ValueError(f"Unknown LLM handler: {name}")

    def _normalize_settings(self, settings: Optional[dict]) -> dict:
        return settings or {}

    def _select_provider(
        self, settings: Optional[dict], provider_key: str, default: str
    ) -> str:
        settings = self._normalize_settings(settings)
        provider = settings.get(provider_key, default) or default
        return provider

    def _select_model(
        self, settings: Optional[dict], provider_key: str, provider: str
    ) -> Optional[str]:
        settings = self._normalize_settings(settings)
        return settings.get(f"{provider_key}_model") or settings.get(
            f"{provider}_model"
        )

    def _get_handler(self, provider: str, model: Optional[str]) -> Optional[Any]:
        if model:
            key = (provider, model)
            if key in self._model_handlers:
                return self._model_handlers[key]
            handler = self._safe_build(provider, model)
            self._model_handlers[key] = handler
            return handler
        if provider in self._handlers:
            return self._handlers[provider]
        handler = self._safe_build(provider, None)
        self._handlers[provider] = handler
        return handler

    def get_handler(
        self,
        settings: Optional[dict],
        provider_key: str = "realtime_llm",
        default: str = "llamacpp",
    ) -> Optional[Any]:
        provider = self._select_provider(settings, provider_key, default)
        model = self._select_model(settings, provider_key, provider)
        handler = self._get_handler(provider, model)
        if handler:
            return handler
        if provider != default:
            handler = self._get_handler(default, None)
            if handler:
                return handler
        for fallback in self._handlers.values():
            if fallback:
                return fallback
        return None

    def _filter_call_kwargs(self, handler: Any, call_kwargs: dict) -> dict:
        if not call_kwargs:
            return {}
        try:
            sig = inspect.signature(handler.call)
        except (TypeError, ValueError):
            return call_kwargs
        allowed = set()
        has_var_kw = False
        for name, param in sig.parameters.items():
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                has_var_kw = True
            if param.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ):
                allowed.add(name)
        if has_var_kw:
            return call_kwargs
        return {key: value for key, value in call_kwargs.items() if key in allowed}

    def call(
        self,
        settings: Optional[dict],
        user_msgs: list[str],
        provider_key: str = "realtime_llm",
        default: str = "llamacpp",
        **kwargs: Any,
    ) -> str:
        handler = self.get_handler(settings, provider_key, default)
        if not handler:
            logging.error("No LLM handler available for %s", provider_key)
            return ""
        call_kwargs = self._filter_call_kwargs(handler, kwargs)
        return handler.call(user_msgs, **call_kwargs)

    def call_citation(
        self,
        settings: Optional[dict],
        user_prompt: str,
        docs: list[str],
        provider_key: str = "realtime_llm",
        default: str = "llamacpp",
    ) -> str:
        handler = self.get_handler(settings, provider_key, default)
        if not handler:
            logging.error("No LLM handler available for %s", provider_key)
            return ""
        if hasattr(handler, "call_citation"):
            return handler.call_citation(user_prompt, docs)
        prompt = user_prompt
        if docs:
            prompt = f"{user_prompt}\n\n" + "\n\n".join(docs)
        return self.call(settings, [prompt], provider_key=provider_key, default=default)

    def get_batch_provider(self, provider_name: Optional[str] = None):
        if provider_name and provider_name in self._batch_providers:
            return self._batch_providers[provider_name]
        for fallback in ("openai", "nebius"):
            if fallback in self._batch_providers:
                return self._batch_providers[fallback]
        logging.error("No batch LLM provider available")
        return None
