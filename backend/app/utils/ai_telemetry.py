# AIMETA P=AI调用遥测_供应商中立usage与成本|R=token归一化_显式价格计算_结果封装|NR=不持久化或调用供应商|E=TokenUsage_AICallResult|X=internal|A=dataclass|D=decimal|S=none|RD=./README.ai
"""Provider-neutral AI usage and explicit pricing contracts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Generic, Iterable, Mapping, Optional, TypeVar


T = TypeVar("T")
U = TypeVar("U")
_TOKENS_PER_MILLION = Decimal(1_000_000)


def _read(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _token_count(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized >= 0 else None


def _decimal(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not normalized.is_finite() or normalized < 0:
        return None
    return normalized


def _decimal_string(value: Decimal) -> str:
    normalized = value.normalize()
    decimal_places = max(6, -normalized.as_tuple().exponent)
    return f"{value:.{decimal_places}f}"


@dataclass(frozen=True)
class TokenUsage:
    """统一后的 token 计量；cache token 是 input_tokens 的子集。"""

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    cache_write_input_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    is_complete: bool = False

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TokenUsage":
        return cls(
            input_tokens=_token_count(payload.get("input_tokens")),
            output_tokens=_token_count(payload.get("output_tokens")),
            total_tokens=_token_count(payload.get("total_tokens")),
            cached_input_tokens=_token_count(payload.get("cached_input_tokens")),
            cache_write_input_tokens=_token_count(payload.get("cache_write_input_tokens")),
            reasoning_tokens=_token_count(payload.get("reasoning_tokens")),
            is_complete=payload.get("is_complete") is True,
        )

    @classmethod
    def combine(cls, usages: Iterable["TokenUsage"]) -> "TokenUsage":
        items = list(usages)
        if not items:
            return cls()

        def total(field: str) -> Optional[int]:
            values = [getattr(item, field) for item in items]
            if any(value is None for value in values):
                return None
            return sum(values)

        return cls(
            input_tokens=total("input_tokens"),
            output_tokens=total("output_tokens"),
            total_tokens=total("total_tokens"),
            cached_input_tokens=total("cached_input_tokens"),
            cache_write_input_tokens=total("cache_write_input_tokens"),
            reasoning_tokens=total("reasoning_tokens"),
            is_complete=all(item.is_complete for item in items),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cache_write_input_tokens": self.cache_write_input_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "is_complete": self.is_complete,
        }


def normalize_openai_usage(raw_usage: Any) -> TokenUsage:
    input_tokens = _token_count(_read(raw_usage, "prompt_tokens"))
    output_tokens = _token_count(_read(raw_usage, "completion_tokens"))
    reported_total = _token_count(_read(raw_usage, "total_tokens"))
    prompt_details = _read(raw_usage, "prompt_tokens_details")
    completion_details = _read(raw_usage, "completion_tokens_details")
    cached_tokens = _token_count(_read(prompt_details, "cached_tokens")) or 0
    reasoning_tokens = _token_count(_read(completion_details, "reasoning_tokens")) or 0
    total_tokens = reported_total
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_input_tokens=cached_tokens,
        cache_write_input_tokens=0,
        reasoning_tokens=reasoning_tokens,
        is_complete=input_tokens is not None and output_tokens is not None,
    )


def normalize_openai_embedding_usage(raw_usage: Any) -> TokenUsage:
    input_tokens = _token_count(_read(raw_usage, "prompt_tokens"))
    total_tokens = _token_count(_read(raw_usage, "total_tokens"))
    if total_tokens is None:
        total_tokens = input_tokens
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=0,
        total_tokens=total_tokens,
        cached_input_tokens=0,
        cache_write_input_tokens=0,
        reasoning_tokens=0,
        is_complete=input_tokens is not None,
    )


def normalize_anthropic_usage(raw_usage: Mapping[str, Any]) -> TokenUsage:
    regular_input = _token_count(raw_usage.get("input_tokens"))
    output_tokens = _token_count(raw_usage.get("output_tokens"))
    cached_tokens = _token_count(raw_usage.get("cache_read_input_tokens")) or 0
    cache_write_tokens = _token_count(raw_usage.get("cache_creation_input_tokens")) or 0
    input_tokens = None
    if regular_input is not None:
        input_tokens = regular_input + cached_tokens + cache_write_tokens
    total_tokens = None
    if input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_input_tokens=cached_tokens,
        cache_write_input_tokens=cache_write_tokens,
        reasoning_tokens=0,
        is_complete=regular_input is not None and output_tokens is not None,
    )


@dataclass(frozen=True)
class AIModelPricing:
    input_price_per_million: Optional[Decimal] = None
    output_price_per_million: Optional[Decimal] = None
    cached_input_price_per_million: Optional[Decimal] = None
    cache_write_input_price_per_million: Optional[Decimal] = None
    currency: Optional[str] = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "AIModelPricing":
        currency = payload.get("pricing_currency")
        normalized_currency = currency.strip().upper() if isinstance(currency, str) else None
        return cls(
            input_price_per_million=_decimal(payload.get("input_price_per_million")),
            output_price_per_million=_decimal(payload.get("output_price_per_million")),
            cached_input_price_per_million=_decimal(payload.get("cached_input_price_per_million")),
            cache_write_input_price_per_million=_decimal(payload.get("cache_write_input_price_per_million")),
            currency=normalized_currency or None,
        )


def calculate_ai_cost(
    usage: TokenUsage,
    pricing: AIModelPricing,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if (
        not usage.is_complete
        or usage.input_tokens is None
        or usage.output_tokens is None
        or usage.cached_input_tokens is None
        or usage.cache_write_input_tokens is None
    ):
        return None, pricing.currency, "usage_unavailable"

    regular_input_tokens = (
        usage.input_tokens
        - usage.cached_input_tokens
        - usage.cache_write_input_tokens
    )
    if regular_input_tokens < 0:
        return None, pricing.currency, "usage_invalid"

    required_prices = (
        (regular_input_tokens, pricing.input_price_per_million),
        (usage.output_tokens, pricing.output_price_per_million),
        (usage.cached_input_tokens, pricing.cached_input_price_per_million),
        (usage.cache_write_input_tokens, pricing.cache_write_input_price_per_million),
    )
    configured_prices = [price for _tokens, price in required_prices if price is not None]
    if not configured_prices:
        return None, pricing.currency, "pricing_unconfigured"
    if any(tokens > 0 and price is None for tokens, price in required_prices):
        return None, pricing.currency, "pricing_incomplete"
    if pricing.currency is None:
        return None, None, "currency_unconfigured"

    amount = sum(
        Decimal(tokens) * (price or Decimal(0)) / _TOKENS_PER_MILLION
        for tokens, price in required_prices
    )
    return _decimal_string(amount), pricing.currency, None


@dataclass(frozen=True)
class AICallResult(Generic[T]):
    """AI 返回值及可审计 telemetry；value 保持调用方原类型。"""

    value: T
    provider_type: str
    model: str
    model_id: Optional[int]
    stage: str
    usage: TokenUsage
    cost_amount: Optional[str]
    cost_currency: Optional[str]
    cost_unknown_reason: Optional[str]

    @classmethod
    def from_config(
        cls,
        value: T,
        *,
        config: Mapping[str, Any],
        usage: TokenUsage,
        stage: str,
    ) -> "AICallResult[T]":
        pricing = AIModelPricing.from_mapping(config)
        amount, currency, unknown_reason = calculate_ai_cost(usage, pricing)
        model_id = config.get("model_id")
        return cls(
            value=value,
            provider_type=str(config.get("provider_type") or "openai_compatible"),
            model=str(config.get("model") or ""),
            model_id=model_id if isinstance(model_id, int) else None,
            stage=stage,
            usage=usage,
            cost_amount=amount,
            cost_currency=currency,
            cost_unknown_reason=unknown_reason,
        )

    def telemetry_dict(self) -> dict[str, Any]:
        return {
            "provider_type": self.provider_type,
            "model": self.model,
            "model_id": self.model_id,
            "stage": self.stage,
            "usage": self.usage.to_dict(),
            "cost": {
                "amount": self.cost_amount,
                "currency": self.cost_currency,
                "is_known": self.cost_unknown_reason is None,
                "unknown_reason": self.cost_unknown_reason,
            },
        }

    def with_value(self, value: U) -> "AICallResult[U]":
        """替换业务返回值，同时保留同一次调用的 telemetry。"""

        return AICallResult(
            value=value,
            provider_type=self.provider_type,
            model=self.model,
            model_id=self.model_id,
            stage=self.stage,
            usage=self.usage,
            cost_amount=self.cost_amount,
            cost_currency=self.cost_currency,
            cost_unknown_reason=self.cost_unknown_reason,
        )


def combine_ai_call_results(
    value: U,
    calls: Iterable[AICallResult[Any]],
) -> AICallResult[U]:
    """严格聚合同一模型调用；任一 usage/cost 未知时聚合结果也保持未知。"""

    items = list(calls)
    if not items:
        raise ValueError("AI 调用聚合至少需要一个结果")

    first = items[0]
    identity = (first.provider_type, first.model, first.model_id, first.stage)
    if any(
        (item.provider_type, item.model, item.model_id, item.stage) != identity
        for item in items[1:]
    ):
        raise ValueError("AI 调用聚合的 provider/model/stage 必须一致")

    usage = TokenUsage.combine(item.usage for item in items)
    unknown_reasons = [
        item.cost_unknown_reason
        for item in items
        if item.cost_unknown_reason is not None
    ]
    non_null_currencies = {
        item.cost_currency for item in items if item.cost_currency is not None
    }
    if len(non_null_currencies) > 1:
        raise ValueError("AI 调用聚合的成本币种必须一致")
    currency = next(iter(non_null_currencies), None)

    if unknown_reasons or not usage.is_complete:
        if "usage_invalid" in unknown_reasons:
            unknown_reason = "usage_invalid"
        elif not usage.is_complete or "usage_unavailable" in unknown_reasons:
            unknown_reason = "usage_unavailable"
        else:
            unknown_reason = unknown_reasons[0]
        amount = None
    else:
        amounts = [_decimal(item.cost_amount) for item in items]
        if any(amount is None for amount in amounts) or currency is None:
            raise ValueError("AI 调用成本 envelope 不完整")
        amount = _decimal_string(
            sum((item for item in amounts if item is not None), Decimal(0))
        )
        unknown_reason = None

    return AICallResult(
        value=value,
        provider_type=first.provider_type,
        model=first.model,
        model_id=first.model_id,
        stage=first.stage,
        usage=usage,
        cost_amount=amount,
        cost_currency=currency,
        cost_unknown_reason=unknown_reason,
    )


__all__ = [
    "AICallResult",
    "AIModelPricing",
    "TokenUsage",
    "calculate_ai_cost",
    "combine_ai_call_results",
    "normalize_anthropic_usage",
    "normalize_openai_embedding_usage",
    "normalize_openai_usage",
]
