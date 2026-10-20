"""
Ticker normalisation and validation utilities for Polygon MCP servers.

Polygon exposes heterogeneous ticker formats depending on asset class. The
helpers below ensure we always interact with the API using canonical symbols so
that downstream modules (discovery, historical data, tool routing) can assume a
consistent contract without relying on brittle heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, Optional, Tuple

from .polygon_ddc_loader import (
    PolygonAssetClass,
    PolygonAssetGroup,
    PolygonNormalizationRule,
    PolygonTransformRule,
)


@dataclass(frozen=True)
class TickerValidationResult:
    """Structured response for ticker validation."""

    normalized: str
    asset_class: PolygonAssetClass
    asset_group: PolygonAssetGroup
    components: Dict[str, str]


_FIAT_CODES = {
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CHF",
    "AUD",
    "NZD",
    "CAD",
    "CNY",
    "CNH",
    "HKD",
    "SGD",
    "SEK",
    "NOK",
    "DKK",
    "ZAR",
    "MXN",
    "PLN",
    "HUF",
    "CZK",
    "ILS",
    "THB",
    "KRW",
    "INR",
    "BRL",
    "TRY",
    "RUB",
    "AED",
    "SAR",
    "CLP",
    "COP",
    "ARS",
    "PEN",
    "RON",
    "PHP",
    "MYR",
    "IDR",
    "TWD",
}


def _float_trim(value: float) -> str:
    """Render floats without trailing zeros or decimal point."""

    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text or "0"


class _CompiledNormalizationRule:
    """Helper that encapsulates catalog-driven normalisation behaviour."""

    def __init__(self, asset_class: PolygonAssetClass, rule: PolygonNormalizationRule):
        self.asset_class = asset_class
        self.rule = rule
        self.prefix = (rule.prefix or "").upper()
        detection = rule.detection
        self.detection_prefixes = [prefix.upper() for prefix in detection.prefixes]
        self.detection_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in detection.patterns
        ]
        self.pattern = (
            re.compile(rule.pattern, re.IGNORECASE) if rule.pattern else None
        )
        self.transforms = rule.transforms

    def matches(self, candidate: str) -> bool:
        upper = candidate.upper()
        trimmed = (
            upper[len(self.prefix) :]
            if self.prefix and upper.startswith(self.prefix)
            else upper
        )

        if self.prefix and upper.startswith(self.prefix):
            return True

        if any(upper.startswith(prefix) for prefix in self.detection_prefixes):
            return True

        for pattern in self.detection_patterns:
            if pattern.match(upper) or pattern.match(trimmed):
                return True

        if self.pattern:
            if self.pattern.match(trimmed) or self.pattern.match(upper):
                return True

        return False

    def score(self, candidate: str) -> int:
        """Provide a relative score for how well this rule fits the ticker."""

        upper = candidate.upper()
        trimmed = (
            upper[len(self.prefix) :]
            if self.prefix and upper.startswith(self.prefix)
            else upper
        )

        score = 0
        if self.prefix and upper.startswith(self.prefix):
            score += 5

        if any(upper.startswith(prefix) for prefix in self.detection_prefixes):
            score += 3

        for pattern in self.detection_patterns:
            if pattern.match(upper):
                score += 1
            if pattern.match(trimmed):
                score += 1

        if self.pattern and self.pattern.match(trimmed):
            score += 4

        return score

    def normalize(self, candidate: str) -> Tuple[str, Dict[str, str]]:
        upper = candidate.upper()
        trimmed = (
            upper[len(self.prefix) :]
            if self.prefix and upper.startswith(self.prefix)
            else upper
        )

        components: Dict[str, str] = {}
        match = None
        if self.pattern:
            match = self.pattern.match(trimmed)
            if not match and upper != trimmed:
                match = self.pattern.match(upper)
        if match:
            components = {
                key: (value.upper() if value is not None else value)
                for key, value in match.groupdict().items()
                if value is not None
            }

        if self.rule.type == "pair" and not components:
            components = self._parse_pair(trimmed)
        elif self.rule.type == "pair_compact" and not components:
            components = self._parse_pair_compact(trimmed)
        elif self.rule.type == "options_contract" and not components:
            raise ValueError("Ticker does not match options contract pattern")

        components = self._apply_transforms(components)
        normalized = self._build_normalized_string(trimmed, components)
        return normalized, components

    def _parse_pair(self, body: str) -> Dict[str, str]:
        separators = [self.rule.separator, "/", "-", " "] if self.rule.separator else ["/", "-", " "]
        for sep in separators:
            if sep and sep in body:
                base, quote = body.split(sep, 1)
                return {"base": base.upper(), "quote": quote.upper()}
        if len(body) == 6:
            return {"base": body[:3].upper(), "quote": body[3:].upper()}
        raise ValueError("Unable to parse forex ticker")

    def _parse_pair_compact(self, body: str) -> Dict[str, str]:
        separators = [self.rule.separator, "-", "/", " "] if self.rule.separator else ["-", "/", " "]
        for sep in separators:
            if sep and sep in body:
                base, quote = body.split(sep, 1)
                return {"base": base.upper(), "quote": quote.upper()}
        if len(body) >= 5:
            base = body[:-3].upper()
            quote = body[-3:].upper()
            return {"base": base, "quote": quote}
        raise ValueError("Unable to parse crypto ticker")

    def _apply_transforms(self, components: Dict[str, str]) -> Dict[str, str]:
        if not self.transforms:
            return components

        transformed = dict(components)

        for name, transform in self.transforms.items():
            if not transform or name not in transformed:
                continue

            value: Optional[str] = transformed[name]
            if value is None:
                continue

            value = self._apply_map(transform, value)
            value, numeric_value = self._apply_numeric(transform, value)
            value = self._apply_format(transform, value, numeric_value)
            transformed[name] = value

        return transformed

    @staticmethod
    def _apply_map(transform: PolygonTransformRule, value: str) -> str:
        if transform.map:
            mapped = (
                transform.map.get(value)
                or transform.map.get(value.lower())
                or transform.map.get(value.upper())
            )
            if mapped is not None:
                return mapped
        return value

    @staticmethod
    def _apply_numeric(
        transform: PolygonTransformRule,
        value: str,
    ) -> Tuple[str, Optional[float]]:
        if transform.divide_by:
            try:
                numeric = float(value)
            except (ValueError, TypeError):
                return value, None
            numeric /= transform.divide_by
            return str(numeric), numeric
        return value, None

    @staticmethod
    def _apply_format(
        transform: PolygonTransformRule,
        value: str,
        numeric_value: Optional[float],
    ) -> str:
        if transform.format == "float_trim":
            target = numeric_value
            if target is None:
                try:
                    target = float(value)
                except (ValueError, TypeError):
                    return value
            return _float_trim(target)

        if transform.format == "upper":
            return value.upper()
        if transform.format == "lower":
            return value.lower()
        return value

    def _build_normalized_string(
        self,
        trimmed: str,
        components: Dict[str, str],
    ) -> str:
        rule_type = self.rule.type

        if rule_type == "options_contract":
            body = trimmed
        elif rule_type == "pair":
            base = components.get("base")
            quote = components.get("quote")
            if not base or not quote:
                raise ValueError("Forex ticker requires base and quote components")
            # Use "/" only if separator is None, not if it's empty string
            separator = self.rule.separator if self.rule.separator is not None else "/"
            body = f"{base}{separator}{quote}"
        elif rule_type == "pair_compact":
            base = components.get("base")
            quote = components.get("quote")
            if not base or not quote:
                raise ValueError("Crypto ticker requires base and quote components")
            separator = self.rule.separator or ""
            body = f"{base}{separator}{quote}"
        else:
            body = trimmed

        body = body.upper()
        return f"{self.prefix}{body}" if self.prefix else body


class TickerValidator:
    """Validate and normalise Polygon tickers across asset classes."""

    def __init__(
        self,
        normalization_rules: Optional[Dict[str, PolygonNormalizationRule]] = None,
    ) -> None:
        self._compiled_rules: Dict[PolygonAssetClass, _CompiledNormalizationRule] = {}
        if normalization_rules:
            for key, rule in normalization_rules.items():
                try:
                    asset_class = PolygonAssetClass(key)
                except ValueError:
                    continue
                self._compiled_rules[asset_class] = _CompiledNormalizationRule(
                    asset_class,
                    rule,
                )

    def detect_asset_class(self, value: str) -> PolygonAssetClass:
        """Infer the asset class based on catalog rules with heuristics fallback."""

        if not value or not value.strip():
            raise ValueError("Ticker value is required")

        candidate = value.strip().upper()

        for asset_class, compiled in self._compiled_rules.items():
            if compiled.matches(candidate):
                return asset_class

        return self._detect_with_fallback(candidate)

    def normalize(
        self,
        ticker: str,
        asset_class: Optional[PolygonAssetClass] = None,
    ) -> TickerValidationResult:
        """Normalize ticker to Polygon's canonical form and determine asset group."""

        if not ticker or not ticker.strip():
            raise ValueError("Ticker value is required")

        clean = ticker.strip().upper()
        inferred = asset_class or self.detect_asset_class(clean)

        compiled_rule = self._compiled_rules.get(inferred)
        if compiled_rule:
            try:
                normalized, components = compiled_rule.normalize(clean)
            except ValueError:
                normalized, components = self._fallback_normalize(inferred, clean)
        else:
            normalized, components = self._fallback_normalize(inferred, clean)

        asset_group = (
            PolygonAssetGroup.OPTIONS
            if inferred is PolygonAssetClass.OPTIONS
            else PolygonAssetGroup.CRYPTO_FX
        )

        return TickerValidationResult(
            normalized=normalized,
            asset_class=inferred,
            asset_group=asset_group,
            components=components,
        )

    def _detect_with_fallback(self, candidate: str) -> PolygonAssetClass:
        if candidate.startswith("O:"):
            return PolygonAssetClass.OPTIONS
        if candidate.startswith("C:"):
            return PolygonAssetClass.FOREX
        if candidate.startswith("X:"):
            return PolygonAssetClass.CRYPTO

        if self._looks_like_option_contract(candidate):
            return PolygonAssetClass.OPTIONS

        body = candidate.split(":", 1)[-1]

        if "-" in body:
            return PolygonAssetClass.CRYPTO
        if "/" in body:
            return PolygonAssetClass.FOREX

        compact = body.replace("/", "").replace("-", "")
        if len(compact) == 6 and compact.isalpha():
            base = compact[:3]
            quote = compact[3:]
            if base in _FIAT_CODES and quote in _FIAT_CODES:
                return PolygonAssetClass.FOREX
            return PolygonAssetClass.CRYPTO
        if len(compact) > 6 and compact.isalnum():
            return PolygonAssetClass.CRYPTO

        raise ValueError(f"Unable to detect asset class for ticker '{candidate}'")

    def _fallback_normalize(
        self,
        asset_class: PolygonAssetClass,
        ticker: str,
    ) -> Tuple[str, Dict[str, str]]:
        if asset_class is PolygonAssetClass.OPTIONS:
            return self._normalize_options(ticker)
        if asset_class is PolygonAssetClass.FOREX:
            return self._normalize_forex(ticker)
        if asset_class is PolygonAssetClass.CRYPTO:
            return self._normalize_crypto(ticker)
        raise ValueError(f"Unsupported asset class '{asset_class}'")

    def _normalize_options(self, ticker: str) -> Tuple[str, Dict[str, str]]:
        body = ticker[2:] if ticker.startswith("O:") else ticker
        if not self._looks_like_option_contract(body):
            raise ValueError(
                "Invalid options ticker format. Expected 'SYMBOLYYMMDDC/PSTRIKE'. "
                f"Got '{ticker}'."
            )

        normalized = ticker if ticker.startswith("O:") else f"O:{body}"
        underlying = body[:-15]
        expiry = body[-15:-9]
        option_type = "call" if body[-9] == "C" else "put"
        strike_raw = body[-8:]
        strike_value = int(strike_raw) / 1000
        strike = ("%.3f" % strike_value).rstrip("0").rstrip(".")

        return normalized, {
            "underlying": underlying,
            "expiry": expiry,
            "option_type": option_type,
            "strike": strike,
        }

    def _normalize_forex(self, ticker: str) -> Tuple[str, Dict[str, str]]:
        body = ticker[2:] if ticker.startswith("C:") else ticker
        compact = body.replace("/", "").replace("-", "")
        if len(compact) != 6 or not compact.isalpha():
            raise ValueError(f"Forex ticker must contain two ISO codes: '{ticker}'")
        base, quote = compact[:3], compact[3:]
        if base not in _FIAT_CODES or quote not in _FIAT_CODES:
            raise ValueError(f"Unsupported forex currency pair '{base}/{quote}'")
        normalized = f"C:{base}{quote}"
        return normalized, {"base": base, "quote": quote}

    def _normalize_crypto(self, ticker: str) -> Tuple[str, Dict[str, str]]:
        body = ticker[2:] if ticker.startswith("X:") else ticker
        if "-" in body:
            base, quote = body.split("-", 1)
        elif "/" in body:
            base, quote = body.split("/", 1)
        else:
            compact = body
            if len(compact) <= 3:
                raise ValueError(f"Unable to infer crypto quote for '{ticker}'")
            base, quote = compact[:-3], compact[-3:]

        base = base.upper()
        quote = quote.upper()
        normalized = f"X:{base}{quote}"
        return normalized, {"base": base, "quote": quote}

    def _looks_like_option_contract(self, ticker: str) -> bool:
        body = ticker[2:] if ticker.startswith("O:") else ticker
        if len(body) < 15:
            return False
        symbol = body[:-15]
        expiry = body[-15:-9]
        type_code = body[-9]
        strike = body[-8:]
        return (
            bool(symbol)
            and expiry.isdigit()
            and type_code in {"C", "P"}
            and strike.isdigit()
        )


__all__ = ["TickerValidationResult", "TickerValidator"]
