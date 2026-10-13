# Model Editor Guide

The Model Editor lets you author, inspect, and test EPICC model documents without
leaving the app.

## What the Editor does

- Loads the selected model into an editable document form
- Edits metadata, parameters, equations, groups, scenarios, report blocks, and presets
- Validates edits against the typed model schema
- Lets you Try in Calculator before saving
- Exports the edited model document as YAML

## Open and close the Editor

1. Select a model in the main dropdown.
2. Click Open Model Editor.
3. Make edits across the editor tabs.
4. Click Cancel to return to the Calculator without exporting.

If validation passes, Try in Calculator becomes enabled and loads the edited (unsaved)
model into the Calculator for testing.

## Core sections

### Metadata

Edit model title, description, and authors.

### Parameters

- Add/remove parameter definitions
- Set labels, types, defaults, bounds, and context
- Organize parameters into groups

### Equations

Define equation expressions that reference parameters/scenario variables.

### Scenarios

Define default scenario rows and labels used by the Calculator comparison UI.

### Report

Define output structure as markdown/table/graph blocks and their displayed content.

### Presets

Define named parameter presets to speed up repeat workflows.

## Current scope

- The editor currently exposes tabs for Metadata, Parameters, Equations, Scenarios, Report, and Presets.
- Figure references exist in the broader model/report system, but there is not currently a dedicated Figures editor tab in the UI.

## Validation behavior

- Validation runs continuously as document edits are made.
- Errors are shown with user-facing location labels and technical detail.
- Try in Calculator is disabled until the document validates.

## Preview mode (Try in Calculator)

When you click Try in Calculator:

- EPICC compiles your in-progress document into a temporary model instance.
- The app switches to Calculator mode with those unsaved edits.
- A warning clarifies this state is temporary and not persisted.
- URL sharing is disabled in preview mode to avoid misleading links.

## Save/export from Editor

Use the editor download/export action to save the current model document as YAML.
This is the artifact you can commit to the repository after local review.

## Good practices

- Keep parameter IDs stable after publication to preserve compatibility.
- Update report blocks when renaming equations they reference.
- Re-run comparison scenarios after major equation or default changes.
- Export and version-control YAML changes together with relevant tests.
