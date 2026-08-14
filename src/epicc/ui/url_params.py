"""Encode and decode model parameters to/from human-readable URL query parameters.

The address bar *is* the permalink, so the query string is written to be read,
copied into a document, and hand-edited:

    ?model=measles&vaccination_rate=0.9&scen.22_cases.label=Small+outbreak

Grammar:

- ``model``: the model slug (the YAML file stem, e.g. ``measles``). Required;
  without it there is nothing to restore.
- ``<param_id>``: an equation-context parameter, keyed by its YAML id. Emitted
  only when the current value differs from the model's default, so a link shows
  exactly what the sender changed and nothing else.
- ``scen.<scenario_id>.<var>``: a scenario-variable override.
- ``scen.<scenario_id>.label``: a scenario label override.
- ``scenarios``: comma-separated ordered scenario ids. Emitted only when the
  scenario set or its order differs from the model's defaults.

``model`` and ``scenarios`` are reserved: a parameter with either id is skipped
rather than written to the URL. Unknown keys are ignored on the way in, so
Streamlit's own query parameters and stray keys are harmless.

Values decoded from the URL are coerced, range-clamped, and validated against
each :class:`~epicc.model.schema.Parameter` spec before they reach a widget.
Anything that cannot be honoured is dropped and reported through the warnings
list rather than failing silently -- hand-edited URLs make typos likely.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

import streamlit as st

from epicc.model.schema import Scenario, ScenarioVars
from epicc.ui.parameters import MAX_SCENARIOS, native_value

if TYPE_CHECKING:
    from epicc.model.base import BaseSimulationModel
    from epicc.model.schema import Parameter

MODEL_KEY = "model"
SCENARIOS_KEY = "scenarios"
_SCEN_PREFIX = "scen."
_LABEL_FIELD = "label"

#: Query keys that can never denote a model parameter.
RESERVED_KEYS = frozenset({MODEL_KEY, SCENARIOS_KEY})

_TRUE_TOKENS = frozenset({"true", "1", "yes", "on"})
_FALSE_TOKENS = frozenset({"false", "0", "no", "off"})


@dataclass
class UrlState:
    """State recovered from the query string.

    ``model_label`` is ``None`` when the slug does not match any known model,
    in which case only ``warnings`` is meaningful.
    """

    slug: str
    model_label: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    scenarios: list[Scenario] | None = None
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Slugs
# --------------------------------------------------------------------------


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def model_slug(model: BaseSimulationModel) -> str:
    """Return the short, URL-friendly identifier for *model*.

    Built-in models are loaded from ``epicc.model.models/<slug>.yaml``, so the
    file stem is the natural slug. Anything without a source path falls back to
    a slugified title.
    """
    source = model.get_source_path()
    if source:
        stem = _slugify(PurePosixPath(source).stem)
        if stem:
            return stem
    return _slugify(model.human_name()) or "model"


def build_slug_registry(
    registry: dict[str, BaseSimulationModel],
) -> dict[str, str]:
    """Map slug -> registry label. On a slug collision the first entry wins."""
    slugs: dict[str, str] = {}
    for label, model in registry.items():
        slugs.setdefault(model_slug(model), label)
    return slugs


# --------------------------------------------------------------------------
# Value formatting and parsing
# --------------------------------------------------------------------------


def _format_value(value: Any, spec: Parameter) -> str:
    """Render a native value as the shortest string that parses back to it."""
    if spec.type == "boolean":
        return "true" if value else "false"
    if spec.type == "integer":
        return str(int(value))
    if spec.type == "number":
        text = repr(float(value))
        return text[:-2] if text.endswith(".0") else text
    return str(value)


def _parse_value(raw: str, spec: Parameter, key: str) -> tuple[Any | None, str | None]:
    """Parse *raw* into a native value for *spec*.

    Returns ``(value, warning_or_None)``. A ``None`` value means the input could
    not be honoured and the accompanying warning explains why.
    """
    text = raw.strip()

    if spec.type in ("integer", "number"):
        try:
            number = float(text)
        except (TypeError, ValueError):
            return None, f"Ignored `{key}={raw}`: expected a number."
        if not math.isfinite(number):
            return None, f"Ignored `{key}={raw}`: expected a finite number."

        cast: Any = int if spec.type == "integer" else float
        value = cast(number)
        if spec.min is not None and value < spec.min:
            value = cast(spec.min)
            return value, (
                f"`{key}={raw}` is below the minimum for {spec.label}; "
                f"used {_format_value(value, spec)} instead."
            )
        if spec.max is not None and value > spec.max:
            value = cast(spec.max)
            return value, (
                f"`{key}={raw}` is above the maximum for {spec.label}; "
                f"used {_format_value(value, spec)} instead."
            )
        return value, None

    if spec.type == "boolean":
        lowered = text.lower()
        if lowered in _TRUE_TOKENS:
            return True, None
        if lowered in _FALSE_TOKENS:
            return False, None
        return None, f"Ignored `{key}={raw}`: expected true or false."

    if spec.type == "enum":
        options = spec.options or {}
        if text in options:
            return text, None
        allowed = ", ".join(options) or "(none)"
        return None, f"Ignored `{key}={raw}`: {spec.label} accepts one of {allowed}."

    return text, None


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------


def encode_state(
    model: BaseSimulationModel,
    params: dict[str, Any],
    scenarios: list[Scenario] | None = None,
    slug: str | None = None,
) -> dict[str, str]:
    """Build the query mapping for the current state of *model*.

    Only values that differ from the model's defaults are included. Pass *slug*
    to name a different model in the link than the one supplying the specs --
    the editor preview does this so its link still reopens the saved model.
    """
    query: dict[str, str] = {MODEL_KEY: slug or model_slug(model)}

    specs: dict[str, Parameter] = model.parameter_specs or {}
    for param_id, spec in specs.items():
        if param_id in RESERVED_KEYS or param_id not in params:
            continue
        current = native_value(params[param_id], spec)
        default = native_value(spec.default, spec)
        if current == default:
            continue
        query[param_id] = _format_value(current, spec)

    query.update(_encode_scenarios(model, scenarios))
    return query


def _encode_scenarios(
    model: BaseSimulationModel,
    scenarios: list[Scenario] | None,
) -> dict[str, str]:
    if not scenarios:
        return {}

    defaults = model.default_scenarios or []
    scen_specs: dict[str, Parameter] = model.scenario_parameter_specs or {}
    default_by_id = {scen.id: scen for scen in defaults}

    query: dict[str, str] = {}
    if [scen.id for scen in scenarios] != [scen.id for scen in defaults]:
        query[SCENARIOS_KEY] = ",".join(scen.id for scen in scenarios)

    for index, scen in enumerate(scenarios):
        base = default_by_id.get(scen.id)
        base_label = base.label if base is not None else _fallback_label(index)
        if scen.label != base_label:
            query[f"{_SCEN_PREFIX}{scen.id}.{_LABEL_FIELD}"] = scen.label

        base_vars = base.vars.model_dump() if base is not None else {}
        current_vars = scen.vars.model_dump()
        for var_name, spec in scen_specs.items():
            if var_name not in current_vars:
                continue
            current = native_value(current_vars[var_name], spec)
            default = native_value(base_vars.get(var_name, spec.default), spec)
            if current == default:
                continue
            query[f"{_SCEN_PREFIX}{scen.id}.{var_name}"] = _format_value(current, spec)

    return query


def _fallback_label(index: int) -> str:
    """Label used for a scenario with no default counterpart.

    Matches the scenario editor's own placeholder so a round trip is stable.
    """
    return f"Scenario {index + 1}"


# --------------------------------------------------------------------------
# Decoding
# --------------------------------------------------------------------------


def decode_state(
    model: BaseSimulationModel,
    query: dict[str, str],
) -> tuple[dict[str, Any], list[Scenario] | None, list[str]]:
    """Decode *query* against *model*.

    Returns ``(param_overrides, scenarios, warnings)``. ``scenarios`` is ``None``
    when the query says nothing about scenarios, so the model's defaults stand.
    """
    warnings: list[str] = []
    values: dict[str, Any] = {}

    specs: dict[str, Parameter] = model.parameter_specs or {}
    for param_id, spec in specs.items():
        if param_id in RESERVED_KEYS or param_id not in query:
            continue
        value, warning = _parse_value(query[param_id], spec, param_id)
        if warning is not None:
            warnings.append(warning)
        if value is not None:
            values[param_id] = value

    # A scenario variable at the top level is a plausible hand-editing mistake:
    # it belongs under a scenario id, so say so rather than ignoring it.
    for var_name, spec in (model.scenario_parameter_specs or {}).items():
        if var_name in query and var_name not in specs:
            warnings.append(
                f"Ignored `{var_name}={query[var_name]}`: {spec.label} is set per "
                f"scenario, as `{_SCEN_PREFIX}<scenario>.{var_name}`."
            )

    scenarios = _decode_scenarios(model, query, warnings)
    return values, scenarios, warnings


def _decode_scenarios(
    model: BaseSimulationModel,
    query: dict[str, str],
    warnings: list[str],
) -> list[Scenario] | None:
    defaults = model.default_scenarios
    if not defaults:
        return None

    scen_specs: dict[str, Parameter] = model.scenario_parameter_specs or {}
    default_by_id = {scen.id: scen for scen in defaults}

    order = [scen.id for scen in defaults]
    touched = False

    raw_order = query.get(SCENARIOS_KEY)
    if raw_order is not None:
        requested = _unique(part.strip() for part in raw_order.split(","))
        if not requested:
            warnings.append(f"Ignored `{SCENARIOS_KEY}={raw_order}`: no scenario ids.")
        else:
            if len(requested) > MAX_SCENARIOS:
                warnings.append(
                    f"`{SCENARIOS_KEY}` listed {len(requested)} scenarios; "
                    f"only the first {MAX_SCENARIOS} were used."
                )
                requested = requested[:MAX_SCENARIOS]
            order = requested
            touched = True

    known = set(order)
    for key in query:
        if not key.startswith(_SCEN_PREFIX):
            continue
        scen_id = key[len(_SCEN_PREFIX) :].rsplit(".", 1)[0]
        if scen_id and scen_id not in known:
            warnings.append(f"Ignored `{key}`: no scenario with id `{scen_id}`.")

    scenarios: list[Scenario] = []
    for index, scen_id in enumerate(order):
        base = default_by_id.get(scen_id)
        label = base.label if base is not None else _fallback_label(index)
        base_vars = base.vars.model_dump() if base is not None else {}

        var_values: dict[str, Any] = {
            var_name: native_value(base_vars.get(var_name, spec.default), spec)
            for var_name, spec in scen_specs.items()
        }

        label_key = f"{_SCEN_PREFIX}{scen_id}.{_LABEL_FIELD}"
        if label_key in query:
            label = query[label_key]
            touched = True

        for var_name, spec in scen_specs.items():
            key = f"{_SCEN_PREFIX}{scen_id}.{var_name}"
            if key not in query:
                continue
            value, warning = _parse_value(query[key], spec, key)
            if warning is not None:
                warnings.append(warning)
            if value is not None:
                var_values[var_name] = value
                touched = True

        scenarios.append(
            Scenario(id=scen_id, label=label, vars=ScenarioVars(**var_values))
        )

    return scenarios if touched else None


def _unique(items: Any) -> list[str]:
    """Drop blanks and duplicates while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


# --------------------------------------------------------------------------
# Streamlit glue
# --------------------------------------------------------------------------


def read_url_state(registry: dict[str, BaseSimulationModel]) -> UrlState | None:
    """Read the current query string. Returns ``None`` when no model is named."""
    query = st.query_params.to_dict()
    slug = query.get(MODEL_KEY, "").strip()
    if not slug:
        return None

    label = build_slug_registry(registry).get(slug)
    if label is None:
        return UrlState(
            slug=slug,
            warnings=[
                f"The link refers to a model named `{slug}`, which is not "
                "available here. Pick a model to continue."
            ],
        )

    values, scenarios, warnings = decode_state(registry[label], query)
    return UrlState(
        slug=slug,
        model_label=label,
        params=values,
        scenarios=scenarios,
        warnings=warnings,
    )


def write_url_state(
    model: BaseSimulationModel,
    params: dict[str, Any],
    scenarios: list[Scenario] | None = None,
    slug: str | None = None,
) -> None:
    """Replace the query string with the current state of *model*.

    Uses ``from_dict`` so parameters returned to their defaults disappear from
    the URL instead of lingering.
    """
    st.query_params.from_dict(encode_state(model, params, scenarios, slug))
