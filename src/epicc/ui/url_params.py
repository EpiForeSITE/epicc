"""Encode and decode model parameters to/from human-readable URL query parameters.

The address bar *is* the permalink, so the query string is written to be read,
copied into a document, and hand-edited:

    ?model=measles&param.vaccination_rate=0.9&scen.22_cases.label=Small+outbreak

Grammar:

- ``model``: the model slug (the YAML file stem, e.g. ``measles``). Required;
  without it there is nothing to restore.
- ``param.<param_id>``: an equation-context parameter, keyed by its YAML id.
  Emitted only when the current value differs from the model's default, so a
  link shows exactly what the sender changed and nothing else.
- ``scen.<scenario_id>.<var>``: a scenario-variable override.
- ``scen.<scenario_id>.label``: a scenario label override.
- ``scenarios``: comma-separated ordered scenario ids. Emitted only when the
  scenario set or its order differs from the model's defaults.

Some top-level key names are reserved (see :data:`RESERVED_KEYS`): ``model`` and
``scenarios`` because this grammar uses them, and Streamlit's ``embed`` /
``embed_options`` because :meth:`st.query_params.from_dict` refuses to set them.
The ``param.`` namespace keeps parameter ids from colliding with any of them.
Unknown keys are ignored on the way in, so stray keys are harmless.

Values decoded from the URL are coerced, range-clamped, and validated against
each :class:`~epicc.model.schema.Parameter` spec before they reach a widget.
Anything that cannot be honoured is dropped and reported through the warnings
list rather than failing silently -- hand-edited URLs make typos likely.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, unquote

import streamlit as st

from epicc.model.schema import Scenario, ScenarioVars
from epicc.ui.parameters import MAX_SCENARIOS, native_value

if TYPE_CHECKING:
    from epicc.model.base import BaseSimulationModel
    from epicc.model.schema import Parameter

MODEL_KEY = "model"
SCENARIOS_KEY = "scenarios"
_PARAM_PREFIX = "param."
_SCEN_PREFIX = "scen."
_LABEL_FIELD = "label"
_EMPTY_SCENARIO_ID_TOKEN = "!"

# Streamlit number inputs serialize through JavaScript and cannot preserve
# integers outside this range.
_MAX_SAFE_INTEGER = (1 << 53) - 1
_MIN_SAFE_INTEGER = -_MAX_SAFE_INTEGER

#: Lowercase query keys that can never denote a model parameter. ``embed`` and
#: ``embed_options`` belong to Streamlit, which raises a ``StreamlitAPIException``
#: if either is set programmatically (case-insensitively).
RESERVED_KEYS = frozenset({MODEL_KEY, SCENARIOS_KEY, "embed", "embed_options"})

_TRUE_TOKENS = frozenset({"true", "1", "yes", "on"})
_FALSE_TOKENS = frozenset({"false", "0", "no", "off"})

#: Longest untrusted fragment echoed back into a warning message.
_MAX_ECHO_CHARS = 80


def is_reserved(key: str) -> bool:
    """Whether *key* is a query key this grammar or Streamlit claims for itself."""
    return key.lower() in RESERVED_KEYS


def _param_key(param_id: str) -> str:
    """Return the namespaced query key for an equation parameter id."""
    return f"{_PARAM_PREFIX}{param_id}"


@dataclass
class UrlState:
    """State recovered from the query string.

    ``model_label`` is ``None`` when the slug matches no known model, or matches
    more than one; in that case only ``warnings`` is meaningful. ``resolved``
    distinguishes the two so the caller can retry later -- a custom model the
    user has yet to upload may still show up.
    """

    slug: str
    model_label: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    scenarios: list[Scenario] | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def resolved(self) -> bool:
        return self.model_label is not None


# --------------------------------------------------------------------------
# Warning text
# --------------------------------------------------------------------------


def _code(text: object) -> str:
    """Render untrusted text as an inline code span safe for ``st.warning``.

    Warnings are rendered as Markdown and quote slugs, keys, and raw values
    straight from the URL. Backticks would close the code span and let the URL
    inject arbitrary Markdown (an image tag, say) into trusted app chrome, and
    newlines would end the paragraph, so both are removed before wrapping.
    """
    flattened = re.sub(r"\s+", " ", str(text)).replace("`", "").strip()
    if len(flattened) > _MAX_ECHO_CHARS:
        flattened = flattened[:_MAX_ECHO_CHARS] + "..."
    return f"`{flattened}`"


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
) -> dict[str, list[str]]:
    """Map slug -> every registry label claiming it.

    Slugs come from file names, so an uploaded ``measles.yaml`` collides with
    the built-in model. Collisions are kept rather than silently resolved: a
    link that could open either calculator should open neither.
    """
    slugs: dict[str, list[str]] = {}
    for label, model in registry.items():
        slugs.setdefault(model_slug(model), []).append(label)
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

    Surrounding whitespace is stripped only where it carries no meaning. String
    and enum values are taken verbatim, so encoding and decoding stay inverses
    of each other for values that legitimately begin or end with a space.
    """
    if spec.type == "integer":
        text = raw.strip()
        try:
            exact = Decimal(text)
        except (InvalidOperation, TypeError, ValueError):
            return None, f"Ignored {_code(f'{key}={raw}')}: expected a number."
        if not exact.is_finite():
            return None, f"Ignored {_code(f'{key}={raw}')}: expected a finite number."
        if exact != exact.to_integral_value():
            return None, f"Ignored {_code(f'{key}={raw}')}: expected a whole number."

        clamped: str | None = None
        if spec.min is not None and exact < Decimal(str(spec.min)):
            exact = Decimal(int(spec.min))
            clamped = "below"
        elif spec.max is not None and exact > Decimal(str(spec.max)):
            exact = Decimal(int(spec.max))
            clamped = "above"

        if exact < _MIN_SAFE_INTEGER or exact > _MAX_SAFE_INTEGER:
            return None, (
                f"Ignored {_code(f'{key}={raw}')}: whole numbers must be between "
                f"{_code(_MIN_SAFE_INTEGER)} and {_code(_MAX_SAFE_INTEGER)}."
            )

        int_value = int(exact)
        if clamped == "below":
            return int_value, (
                f"{_code(f'{key}={raw}')} is below the minimum for "
                f"{_code(spec.label)}; used "
                f"{_code(_format_value(int_value, spec))} instead."
            )
        if clamped == "above":
            return int_value, (
                f"{_code(f'{key}={raw}')} is above the maximum for "
                f"{_code(spec.label)}; used "
                f"{_code(_format_value(int_value, spec))} instead."
            )
        return int_value, None

    if spec.type == "number":
        text = raw.strip()
        try:
            number = float(text)
        except (TypeError, ValueError):
            return None, f"Ignored {_code(f'{key}={raw}')}: expected a number."
        if not math.isfinite(number):
            return None, f"Ignored {_code(f'{key}={raw}')}: expected a finite number."
        if spec.min is not None and number < spec.min:
            number = float(spec.min)
            return number, (
                f"{_code(f'{key}={raw}')} is below the minimum for "
                f"{_code(spec.label)}; used {_code(_format_value(number, spec))} instead."
            )
        if spec.max is not None and number > spec.max:
            number = float(spec.max)
            return number, (
                f"{_code(f'{key}={raw}')} is above the maximum for "
                f"{_code(spec.label)}; used {_code(_format_value(number, spec))} instead."
            )
        return number, None

    if spec.type == "boolean":
        lowered = raw.strip().lower()
        if lowered in _TRUE_TOKENS:
            return True, None
        if lowered in _FALSE_TOKENS:
            return False, None
        return None, f"Ignored {_code(f'{key}={raw}')}: expected true or false."

    if spec.type == "enum":
        options = spec.options or {}
        if raw in options:
            return raw, None
        allowed = ", ".join(options) or "(none)"
        return None, (
            f"Ignored {_code(f'{key}={raw}')}: {_code(spec.label)} accepts one of "
            f"{_code(allowed)}."
        )

    return raw, None


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------


def encode_state(
    model: BaseSimulationModel,
    params: dict[str, Any],
    scenarios: list[Scenario] | None = None,
) -> dict[str, str]:
    """Build the query mapping for the current state of *model*.

    Only values that differ from the model's defaults are included.
    """
    query: dict[str, str] = {MODEL_KEY: model_slug(model)}

    specs: dict[str, Parameter] = model.parameter_specs or {}
    for param_id, spec in specs.items():
        if param_id not in params:
            continue
        current = native_value(params[param_id], spec)
        default = native_value(spec.default, spec)
        if current == default:
            continue
        query[_param_key(param_id)] = _format_value(current, spec)

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
        query[SCENARIOS_KEY] = ",".join(_quote_id(scen.id) for scen in scenarios)

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


def _quote_id(scen_id: str) -> str:
    """Percent-encode a scenario id for the comma-separated ``scenarios`` list.

    Ordinary ids (``22_cases``) pass through untouched. Delimiters are escaped,
    and an empty id uses a token that cannot collide with a literal id, so the
    list stays unambiguous without becoming unreadable in the common case.
    """
    if scen_id == "":
        return _EMPTY_SCENARIO_ID_TOKEN
    return quote(scen_id, safe="")


def _unquote_id(token: str) -> str:
    """Reverse :func:`_quote_id` without conflating empty and literal ids."""
    if token == _EMPTY_SCENARIO_ID_TOKEN:
        return ""
    return unquote(token)


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
        key = _param_key(param_id)
        if key not in query:
            continue
        value, warning = _parse_value(query[key], spec, key)
        if warning is not None:
            warnings.append(warning)
        if value is not None:
            values[param_id] = value

    # A scenario variable under param. is a plausible hand-editing mistake: it
    # belongs under a scenario id, so say so rather than ignoring it.
    for var_name, spec in (model.scenario_parameter_specs or {}).items():
        key = _param_key(var_name)
        if key in query and var_name not in specs:
            warnings.append(
                f"Ignored {_code(f'{key}={query[key]}')}: {_code(spec.label)} "
                f"is set per scenario, as {_code(f'{_SCEN_PREFIX}<scenario>.{var_name}')}."
            )

    # So is dropping the namespace entirely. Bare parameter names look right and
    # would otherwise be ignored as unknown keys, leaving defaults in place.
    for param_id in _unique([*specs, *(model.scenario_parameter_specs or {})]):
        if param_id in query and not is_reserved(param_id):
            warnings.append(
                f"Ignored {_code(f'{param_id}={query[param_id]}')}: parameters need "
                f"the {_code(_PARAM_PREFIX)} prefix, as {_code(_param_key(param_id))}."
            )

    scenarios = _decode_scenarios(model, query, warnings)
    return values, scenarios, warnings


def _split_scen_key(key: str) -> tuple[str, str] | None:
    """Split ``scen.<id>.<field>`` into ``(id, field)``.

    Uses the *last* dot as the separator, so scenario ids containing dots work.
    """
    scen_id, separator, scen_field = key[len(_SCEN_PREFIX) :].rpartition(".")
    if not separator:
        return None
    return scen_id, scen_field


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
        tokens = [part.strip() for part in raw_order.split(",") if part.strip()]
        requested = _unique(_unquote_id(token) for token in tokens)
        if not requested:
            warnings.append(
                f"Ignored {_code(f'{SCENARIOS_KEY}={raw_order}')}: no scenario ids."
            )
        else:
            if len(requested) > MAX_SCENARIOS:
                warnings.append(
                    f"{_code(SCENARIOS_KEY)} listed {len(requested)} scenarios; "
                    f"only the first {MAX_SCENARIOS} were used."
                )
                requested = requested[:MAX_SCENARIOS]
            order = requested
            touched = True

    known_ids = set(order)
    known_fields = {_LABEL_FIELD} | set(scen_specs)
    for key in query:
        if not key.startswith(_SCEN_PREFIX):
            continue
        parts = _split_scen_key(key)
        if parts is None:
            warnings.append(
                f"Ignored {_code(key)}: expected "
                f"{_code(f'{_SCEN_PREFIX}<scenario>.<field>')}."
            )
            continue
        scen_id, scen_field = parts
        if scen_id not in known_ids:
            warnings.append(f"Ignored {_code(key)}: no scenario with id {_code(scen_id)}.")
        elif scen_field not in known_fields:
            allowed = ", ".join(sorted(known_fields))
            warnings.append(
                f"Ignored {_code(key)}: scenarios accept {_code(allowed)}."
            )

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
    """Drop duplicates while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# --------------------------------------------------------------------------
# Streamlit glue
# --------------------------------------------------------------------------


def read_url_state(
    registry: dict[str, BaseSimulationModel],
    *,
    preferred_label: str | None = None,
) -> UrlState | None:
    """Read the query string, using an explicit selection to break slug ties."""
    query = st.query_params.to_dict()
    slug = query.get(MODEL_KEY, "").strip()
    if not slug:
        return None

    candidates = build_slug_registry(registry).get(slug, [])
    if preferred_label is not None and preferred_label in candidates:
        label = preferred_label
    elif len(candidates) > 1:
        return UrlState(
            slug=slug,
            warnings=[
                f"The link refers to {_code(slug)}, but more than one loaded model "
                "goes by that name. Pick the one you meant from the model list."
            ],
        )
    elif not candidates:
        return UrlState(
            slug=slug,
            warnings=[
                f"The link refers to a model named {_code(slug)}, which isn't "
                "loaded here. Load that model and the link's values will be applied."
            ],
        )
    else:
        label = candidates[0]

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
) -> None:
    """Replace the query string with the current state of *model*.

    Uses ``from_dict`` so parameters returned to their defaults disappear from
    the URL instead of lingering.

    Called on every script run, most of which change nothing. Writing anyway
    would still cost a history entry each time: Streamlit answers a query-param
    update by calling ``history.pushState``, and browsers keep only the last
    ~50 entries per tab, so a session's worth of no-op writes pushes whatever
    the user was browsing before out of Back's reach.
    """
    query = encode_state(model, params, scenarios)
    if query == st.query_params.to_dict():
        return
    st.query_params.from_dict(query)


def clear_url_state() -> None:
    """Drop the state from the URL, leaving Streamlit's own keys in place.

    Used when the on-screen state cannot honestly be expressed as a link, so
    that no stale or misleading permalink is left behind. Like
    :func:`write_url_state`, silent when there is nothing to change.
    """
    if not st.query_params.to_dict():
        return
    st.query_params.clear()
