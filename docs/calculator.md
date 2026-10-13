# Calculator Guide

The Calculator is the main EPICC workflow for running epidemiological cost models,
comparing scenarios, and exporting outputs.

## What the Calculator does

- Loads a model (built-in or uploaded)
- Lets you edit parameter values and scenario assumptions
- Runs model equations and shows scenario-by-scenario outputs
- Renders report sections (text, tables, charts, and placeholders where applicable)
- Exports parameters and report artifacts

## Basic workflow

1. Select a model from the model dropdown.
2. Review and edit sidebar inputs.
3. Click Run simulation.
4. Review report tables and charts.
5. Export results or parameters as needed.

## Inputs and validation

- Parameter inputs are type-checked and range-checked.
- Invalid values surface as validation messages in the UI.
- Scenario-specific inputs are kept separate from global equation parameters.

## Sharing and reproducibility

- EPICC keeps URL query parameters synchronized with your non-default inputs.
- Copying the page URL shares the current model + edited inputs.
- If a model slug is ambiguous (duplicate YAML stem), link sharing is disabled for safety.
- Unsaved Model Editor previews are not shareable by URL.

## Export options

### Parameter export

Use Save Changes as Preset to export current inputs as YAML or XLSX.

### Report export

- Save report as PDF: opens browser print flow for print-ready sharing.

## Common troubleshooting

### Run button disabled

Usually caused by unresolved input validation errors. Fix highlighted fields and rerun.

### URL did not apply all values

If a linked model is not loaded yet (for example uploaded later), URL values stay pending
until that model is available.

### DOCX export unavailable or partial

Current main-branch UI does not expose a DOCX report export button.
