### Epidemiologist

1. As an epidemiologist, I want to select a disease so that all relevant costs are already populated.
2. As an epidemiologist, I want to specify how many outbreak scenarios are included in the model so that it provides multiple points of comparison.
3. As an epidemiologist, I want the app to include guardrails against generating misleading output, with a warning shown in worst-case scenarios.
4. As an epidemiologist who is a heavy spreadsheet user, I want to author or edit model parameters in XLSX instead of hand-editing a YAML file, so the tool doesn't require technical file-format knowledge.
5. As an epidemiologist, I want to download a documented parameter template (YAML or XLSX), specialize it with my own values, and load it back into the app.

**Status:** All of these are implemented. Nested columnar data may be worked with in YAML or XLSX (it all goes through the same code). All relevant costs are already populated per default values or presets as needed, and checked against a dynamically generated Pydantic model at update time to help ensure correctness.

### Public Health Official / SLTT Staff

1. As a public health official, I want to generate a report with a summary so I can share it directly with lawmakers, the general public, or other epidemiologists.
2. As a public health official, I want to export that report as a PDF so I have a standard, print-ready format to distribute.
3. As a public health official, I want to open a parameter file someone emailed me (YAML or XLSX) directly in Excel or a file previewer, without launching the app, just to see what's in it before deciding to load it.

**Status:** Report generation is not yet complete (at least as far as DOCX is concerned). Reports can be exported as PDF, but the output quality and formatting are still limited. EPICC does not need to add functionality for previewing parameter files, since this is handled by standard OS and spreadsheet tooling.

### Any User

1. As any user, I want to save the current state of the model so I can share it and reuse it later.
2. As any user, I want to reload a previously saved or shared parameter file back into the app.
3. As any user, I want to read the assumptions behind the model (a longer description, not just numbers) so I can justify the figures to others.
4. As any user, I want my in-progress configuration to persist if I accidentally close or refresh the app, so I don't lose my work.
   - *Unsure the best way to do this.*
5. As any user authoring my own parameter file, I want clear validation error messages when the file is malformed or missing required fields, so I can fix it myself.

**Status:** Yes, exporting/importing is a common feature throughout the cost calculator. Model parameters may include help text and references to aid in future understanding and documentation. All is checked against a dynamically generated Pydantic model at update time to help ensure correctness.

### Developer

1. As a developer, I want the app to be modular so I can extend it easily to other diseases.
2. As a developer, I want a unified read/write abstraction across parameter formats (YAML, XLSX, and future formats like CSV), so adding a new format later doesn't require rebuilding the validation layer.

**Status:** The app is modular, and so is the parameter loading system.
