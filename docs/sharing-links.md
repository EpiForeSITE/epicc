# Sharing links

The address bar is a permalink. As you change parameters the app rewrites the query
string, so copying the URL is enough to hand someone the exact calculation you are
looking at.

The query string is meant to be read — and edited — by hand:

```
https://epiworldpythonapp.streamlit.app/?model=measles&param.vaccination_rate=0.9&scen.22_cases.label=Small+outbreak&scen.22_cases.n_cases=30
```

| Key | Meaning |
| --- | --- |
| `model` | Which model to open, named by its YAML file stem (`measles`, `measles_oregon`, `tb_isolation`). Required. |
| `param.<parameter>` | An equation parameter value, keyed by its id in the model YAML. |
| `scen.<scenario>.<variable>` | A scenario variable, keyed by scenario id. |
| `scen.<scenario>.label` | A scenario's display label. |
| `scenarios` | Comma-separated scenario ids, in order. Only needed if you add, remove, or reorder scenarios. |

Only values that differ from the model's defaults appear, so a link shows exactly what
was changed and nothing else. Open a model without changing anything and the URL stays
at `?model=measles`.

Because links carry changes rather than a full snapshot, a link opened after the model's
defaults change will pick up the new defaults for everything it does not mention. Use the
parameter export (**Save Changes as Preset**) when you need a calculation pinned exactly.

Keys the app does not recognise are ignored. Values that cannot be honoured are reported
with a warning in the app rather than failing silently: a number past its model-declared
range is clamped to the range, while an unknown option, a fractional or browser-unsafe
whole number, or a misspelled key is dropped. Equation parameters live under `param.`,
so even ids such as `model`, `scenarios`, `embed`, and `embed_options` cannot collide
with the app's or Streamlit's top-level query keys. Write a parameter without that
prefix and the app says so, rather than treating it as a stray key and leaving the
default in place.

A model that isn't loaded in the browser — an uploaded one, or one from a newer version
of the app — leaves its link pending with a warning; load that model and its values are
applied then. If multiple loaded models use the same YAML filename, link sharing is
disabled until the custom file is renamed, because its short URL name would be ambiguous.
While you are trying unsaved edits from the model editor, the URL is also cleared: a link
can carry parameter values but not the edits themselves, so it would reopen the saved
model showing different numbers.
