# Tutorial: Build a Simple Model

This tutorial walks through a minimal EPICC model you can copy, load, and run.
It is intentionally small so you can learn the model structure quickly.

## Goal

Create a two-scenario model that compares total cost across different case counts.

## Step 1: Create a model YAML file

Create a file named `simple_cost_model.yaml` with this content:

```yaml
title: Simple Cost Comparison
description: Minimal tutorial model for comparing outbreak costs.
authors:
  - name: EPICC tutorial

parameters:
  cost_per_case:
    type: number
    label: Cost per case
    description: Average direct + indirect cost for each case.
    default: 10000
    min: 0
    unit: USD
    context: equation

  n_cases:
    type: integer
    label: Number of cases
    description: Scenario-specific case count.
    default: 20
    min: 0
    context: scenario

equations:
  eq_total_cost:
    label: Total cost
    unit: USD
    output: number
    compute: n_cases * cost_per_case

groups:
  - label: Cost assumptions
    children:
      - cost_per_case

scenarios:
  - id: baseline
    label: Baseline outbreak
    vars:
      n_cases: 20

  - id: surge
    label: Surge outbreak
    vars:
      n_cases: 120

report:
  - type: markdown
    content: |
      ## Overview
      This tutorial report compares total costs across two outbreak scenarios.

  - type: table
    caption: Total cost by scenario
    rows:
      - label: Total cost
        value: eq_total_cost

  - type: graph
    kind: bar
    title: Total cost comparison
    caption: Baseline vs surge
    rows:
      - label: Total cost
        value: eq_total_cost

figures: []

presets:
  - id: high_cost
    label: Higher cost assumption
    params:
      cost_per_case: 15000
```

## Step 2: Load it in EPICC

1. Start the app.
2. Use the model upload action.
3. Select `simple_cost_model.yaml`.
4. Choose the uploaded model in the model selector.

## Step 3: Run the model

1. Confirm `cost_per_case` in the parameter panel.
2. Click Run Simulation.
3. Review:
   - the markdown block
   - the table showing `eq_total_cost`
   - the bar chart comparing scenarios

## Step 4: Try simple edits

- Change `cost_per_case` and rerun.
- Add another scenario in the Model Editor and rerun.
- Add another report row/equation and observe the table/chart update.

## Step 5: Export and share

- Use Save Changes as Preset to export parameter values.
- Use Save report as PDF to share the output.

## Common pitfalls

- If a report row shows missing values, verify `rows[].value` matches an equation ID.
- If scenario values do not change, verify the parameter uses `context: scenario`.
- If validation fails, check data types (`integer` vs `number`) and min/max bounds.
