# Model Reference

This page explains the model format in plain language, with practical examples you can copy and adapt.

- Generated schema: [Model schema reference](schema.md)
- Source of truth: [src/epicc/model/schema.py](../src/epicc/model/schema.py)

## Quick model skeleton

Most models follow this shape at the top level:

```yaml
title: Example model
description: Minimal example
authors:
  - name: Example Author
    email: author@example.org

parameters: {}
equations: {}
groups: []
scenarios: []
report: []
figures: []
presets: []
```

## Parameters

Parameters are the user inputs shown in the app. In most cases, each parameter includes:

- `type` (what kind of value it accepts)
- `label` (how it appears in the UI)
- `default` (starting value)

```yaml
parameters:
  cost_per_case:
    type: number
    label: Cost per case
    default: 12500
    min: 0
    unit: USD
    context: equation

  n_cases:
    type: integer
    label: Number of cases
    default: 22
    min: 0
    context: scenario

  intervention:
    type: enum
    label: Intervention level
    default: standard
    options:
      standard: Standard protocol
      enhanced: Enhanced response
```

How context works:
- `context: equation` means one shared value in the sidebar.
- `context: scenario` means one value per scenario.
- `enum` parameters must include `options`.

## Equations

Equations define calculated values. Each `compute` expression can reference parameter names, scenario variables, and previously computed equations.

```yaml
equations:
  eq_hosp:
    label: Hospitalization
    output: number
    compute: n_cases * cost_per_case

  eq_total:
    label: Total cost
    output: number
    compute: eq_hosp
```

Notes:
- `output` can be `number`, `integer`, or omitted.
- Equation IDs are referenced by report rows.

## Scenarios

Scenarios are the side-by-side comparisons in your report. Each scenario has an `id`, a user-facing `label`, and a `vars` block for scenario-specific values.

```yaml
scenarios:
  - id: small_outbreak
    label: Small outbreak
    vars:
      n_cases: 22

  - id: medium_outbreak
    label: Medium outbreak
    vars:
      n_cases: 100
```

## Report blocks

The `report` list is rendered from top to bottom. Each entry is one block in the output.

Available block types:
- `markdown`
- `table`
- `graph`
- `figure`

### Markdown block

```yaml
- type: markdown
  content: |
    ## Overview
    This report compares scenarios.
```

### Table block

```yaml
- type: table
  caption: Estimated costs by scenario
  columns: [small_outbreak, medium_outbreak]
  rows:
    - label: Hospitalization
      value: eq_hosp
    - label: Total
      value: eq_total
      emphasis: strong
```

### Graph block

```yaml
- type: graph
  kind: bar
  title: Total cost comparison
  caption: Cost per scenario
  rows:
    - label: Total
      value: eq_total
```

`kind` options: `bar`, `stacked_bar`, `line`, `pie`.

### Figure block

```yaml
- type: figure
  id: fig_example
```

Figure blocks reference entries in the top-level `figures` list.

## Figures

Use `figures` to define reusable figure metadata and optional plotting code.

```yaml
figures:
  - id: fig_example
    title: Example figure
    alt-text: Example output figure
    py-code: |
      # optional future/advanced figure code
```

## Presets

Presets are saved bundles of parameter values you can reuse.

```yaml
presets:
  - id: high_cost
    label: High cost assumptions
    params:
      cost_per_case: 15000
```

## Common mistakes

- Defining an `enum` parameter without `options`.
- Referencing an unknown equation ID in `report.rows[].value`.
- Adding scenario variables that do not match scenario-context parameters.
- Using scenario IDs in `columns` that are not defined in `scenarios`.
