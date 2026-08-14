# epicc

Streamlit webapp for epiworld.

Please install dependencies with a dependency manager capable of reading `pyproject.toml` files
(most modern solutions will work). For example, with [`uv`](https://docs.astral.sh/uv/):

```
uv sync
```

Please note that this step is not required if working in a containerized context.

You may then run with:

```
uv run -m streamlit run app.py
```

## Launch the App online

Click below to open the live Streamlit application, as currently deployed:

https://epiworldpythonapp.streamlit.app/

*(If the app is still deploying, it may take a few seconds to load.)*

Please follow instructions in your console for loading development versions.

## Sharing a calculation by URL

The address bar is a permalink. As you change parameters the app rewrites the query
string, so copying the URL is enough to hand someone the exact calculation you are
looking at.

The query string is meant to be read — and edited — by hand:

```
https://epiworldpythonapp.streamlit.app/?model=measles&vaccination_rate=0.9&scen.22_cases.label=Small+outbreak&scen.22_cases.n_cases=30
```

| Key | Meaning |
| --- | --- |
| `model` | Which model to open, named by its YAML file stem (`measles`, `tb_isolation`). Required. |
| `<parameter>` | A parameter value, keyed by its id in the model YAML. |
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
with a warning in the app rather than failing silently: a number past its allowed range
is clamped to the range, and an unknown option, a fractional value for a whole-number
parameter, or a misspelled key is dropped. `model`, `scenarios`, and Streamlit's own
`embed` and `embed_options` are reserved key names and cannot be used as parameter ids.

Two cases produce no link. A model that isn't loaded in the browser — an uploaded one, or
one from a newer version of the app — leaves the link pending with a warning; load that
model and its values are applied then. And while you are trying unsaved edits from the
model editor, the URL is cleared, because a link can carry parameter values but not the
edits themselves, so it would reopen the saved model showing different numbers.

## Versioning and release notes

The project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). The
current version appears next to the title in the app header, and the **What's new**
button links to the
[latest release](https://github.com/EpiForeSITE/epicc/releases/latest).

Release notes are not kept in the repository. GitHub generates them from the pull
requests merged since the previous release, so the only thing that shapes them is how
you title your PRs. To cut a release:

```
make bump BUMP=minor          # or BUMP=patch / BUMP=major, or VERSION=1.2.3
```

That updates the version in `src/epicc/__init__.py` and `pyproject.toml`, then prints
the commands to finish:

```
git commit -am "Release v0.2.0"
git tag -a v0.2.0 -m "v0.2.0"
git push --follow-tags
```

Pushing the tag triggers [`release.yml`](.github/workflows/release.yml), which publishes
the GitHub release with generated notes. The app's **What's new** link then points at it
with no further action. `make test` fails if `pyproject.toml` and `epicc.__version__`
ever disagree, and the release workflow refuses a tag that does not match the source.

## Branding and themes

The app's identity is configured in
[`src/epicc/config/default.yaml`](src/epicc/config/default.yaml). This keeps the
application title, logos, font stack, and light/dark color palettes together in
one YAML file.

```yaml
app:
  title: Epidemiological Cost Calculator (EPICC)

brand:
  name: ForeSITE
  font_family: '"Proxima Nova", "Avenir Next", Avenir, "Helvetica Neue", Arial, sans-serif'
  logo:
    path: web/assets/foresite-primary-rgb.png
    dark_path: web/assets/foresite-white-rgb.png
    alt_text: ForeSITE logo
    mime_type: image/png
    width_px: 220
  colors: # Light mode
    primary: "#A60F2D"
    on_primary: "#FFFFFF"
    accent: "#FDB921"
    text: "#4E4E4E"
    muted_text: "#6B6E72"
    canvas: "#F7F7F5"
    surface: "#FFFFFF"
    border: "#D9D9D6"
    chart_palette: ["#A60F2D", "#FDB921", "#4E4E4E", "#6B6E72"]
  dark_colors: # Dark mode
    primary: "#FDB921"
    on_primary: "#231F20"
    accent: "#A60F2D"
    text: "#F3F1ED"
    muted_text: "#B8B3AD"
    canvas: "#171717"
    surface: "#242424"
    border: "#4E4E4E"
    chart_palette: ["#FDB921", "#A60F2D", "#F3F1ED", "#B8B3AD"]
```

`colors` controls the light palette and `dark_colors` controls the dark palette.
Each needs the same semantic fields; `on_primary` is the text/icon color used on
primary buttons. `dark_colors` and `logo.dark_path` are optional, so existing
brand configurations continue to work and fall back to the light values.

Visitors choose **System**, **Light**, or **Dark** from Streamlit's menu in the
top-right corner. The app mirrors that choice automatically, including switching
to `logo.dark_path` when dark mode is active.

After changing branding, rebuild the static app before deployment:

```bash
make build
```
