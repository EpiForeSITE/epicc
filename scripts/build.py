from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


def cli():
    parser = argparse.ArgumentParser(
        description="Build stlite bundle from pyproject.toml"
    )

    parser.add_argument(
        "--app",
        default="app.py",
        help="Path to Streamlit entrypoint (default: app.py)",
    )
    parser.add_argument(
        "--out",
        default="dist",
        help="Output path for generated bundle (default: dist)",
    )

    return parser


def strip_dependency_name(dep: str) -> str:
    name = dep.split("[")[0]
    for op in (">=", "==", "<=", ">", "<", "~=", "!="):
        name = name.split(op)[0]

    return name.strip()


def load_config(pyproject_path: Path) -> dict:
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    deps = pyproject.get("project", {}).get("dependencies", [])
    packages = [strip_dependency_name(dep) for dep in deps]
    stlite_config = pyproject.get("tool", {}).get("stlite", {})
    required_fields = ["mount_dirs", "text_suffixes", "title", "css_url", "js_url"]
    missing = [field for field in required_fields if field not in stlite_config]

    if missing:
        print(
            f"Error: Missing required fields in [tool.stlite]: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    return {
        "packages": packages,
        "mount_dirs": tuple(stlite_config["mount_dirs"]),
        "text_suffixes": tuple(stlite_config["text_suffixes"]),
        "title": stlite_config["title"],
        "css_url": stlite_config["css_url"],
        "js_url": stlite_config["js_url"],
    }


def should_mount_file(path: Path, text_suffixes: tuple[str, ...]) -> bool:
    if not path.is_file():
        return False

    if path.name.startswith("."):
        return False

    if "__pycache__" in path.parts:
        return False

    if path.suffix in (".pyc", ".pyo"):
        return False

    return path.suffix.lower() in text_suffixes


def hash_content(content: str) -> str:
    """Bust those caches! Generate a short hash of the content (Python files) to bust browser caches."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_hashed_filename(path: str, content: str) -> str:
    """
    Examples:
        "app.py" + content -> "app.abc12345.py"
        "src/epicc/__init__.py" + content -> "src/epicc/__init__.def67890.py"
    """

    file_hash = hash_content(content)

    if "." in Path(path).name:
        stem = Path(path).stem
        suffix = Path(path).suffix
        parent = Path(path).parent

        hashed_name = f"{stem}.{file_hash}{suffix}"
        return str(parent / hashed_name) if parent != Path(".") else hashed_name
    else:
        return f"{path}.{file_hash}"


def collect_files(
    project_root: Path,
    app_path: Path,
    mount_dirs: tuple[str, ...],
    text_suffixes: tuple[str, ...],
) -> dict[str, str]:
    """Collect source files to mount in the stlite virtual filesystem.

    Returns:
        dict mapping relative paths to file contents
    """
    mounted_files: dict[str, str] = {}
    files_to_mount: list[Path] = [app_path]

    # Scan configured directories, read, and then mount eligible files
    for dirname in mount_dirs:
        directory = project_root / dirname
        if directory.exists():
            files_to_mount.extend(sorted(directory.rglob("*")))

    for path in files_to_mount:
        if not should_mount_file(path, text_suffixes):
            continue

        try:
            relative_path = path.relative_to(project_root).as_posix()
            mounted_files[relative_path] = path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"warning: I could not read {path}: {e}", file=sys.stderr)

    return mounted_files


def write_source_files(
    mounted_files: dict[str, str],
    output_dir: Path,
) -> dict[str, str]:
    """Write source files to output directory with content hashes."""
    path_mapping = {}

    for relative_path, content in mounted_files.items():
        # Generate hashed filename
        hashed_path = get_hashed_filename(relative_path, content)

        # Full output path
        output_path = output_dir / "files" / hashed_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        output_path.write_text(content, encoding="utf-8")

        # Store mapping for config (relative to output_dir)
        url_path = f"./files/{hashed_path}"
        path_mapping[relative_path] = url_path

    return path_mapping


def get_stlite_config_file(
    *,
    entrypoint: str,
    packages: list[str],
    file_urls: dict[str, str],
    output_dir: Path,
) -> dict[str, Any]:
    return {
        "entrypoint": entrypoint,
        "requirements": packages,
        "files": {
            original_path: {"url": url} for original_path, url in file_urls.items()
        },
    }


def build_loader_html(
    *,
    title: str,
    css_url: str,
    js_url: str,
) -> str:
    title_html = html.escape(title, quote=True)
    css_html = html.escape(css_url, quote=True)
    js_json = json.dumps(js_url)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />

    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="description" content="Calculate and analyze epidemiological costs" />
    <meta name="keywords" content="epidemiology, cost calculator, public health, analysis" />
    <meta name="author" content="ForeSITE -- Forecasting and Surveillance of Infectious Threats and Epidemics" />

    <meta name="theme-color" content="#ffffff" />
    <meta name="mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-status-bar-style" content="default" />
    <meta name="apple-mobile-web-app-title" content="epicc" />

    <meta property="og:type" content="website" />
    <meta property="og:title" content="{title_html}" />
    <meta property="og:description" content="Calculate and analyze epidemiological costs" />
    <meta property="og:url" content="https://epiForeSITE.github.io/epicc" />

    <!-- TODO: Favicon -->
    <!-- <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png" /> -->
    <!-- <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png" /> -->
    <!-- <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" /> -->
    
    <title>{title_html}</title>
    <link rel="stylesheet" href="{css_html}" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module">
      import {{ mount }} from {js_json};

      const config = await fetch('./stlite-config.json')
        .then(response => response.json());

      const root = document.getElementById("root");
      mount(config, root);
    </script>
  </body>
</html>
"""


def main():
    args = cli().parse_args()

    # Resolve paths
    script_path = Path(__file__).resolve()
    maybe_project_root = script_path.parent

    while True:
        if (maybe_project_root / "pyproject.toml").exists():
            project_root = maybe_project_root
            break

        if maybe_project_root.parent == maybe_project_root:
            print(
                "Error: Could not find pyproject.toml in any parent directory",
                file=sys.stderr,
            )
            return 1

        maybe_project_root = maybe_project_root.parent

    project_root = maybe_project_root
    pyproject_path = project_root / "pyproject.toml"
    assert pyproject_path.exists()

    # Load configuration
    config = load_config(pyproject_path)

    # Validate app file exists
    app_path = (project_root / args.app).resolve()
    if not app_path.exists():
        print(f"Error: App file not found at {app_path}", file=sys.stderr)
        return 1

    # Collect files to mount
    print("Collecting files...", file=sys.stderr)
    mounted_files = collect_files(
        project_root,
        app_path,
        config["mount_dirs"],
        config["text_suffixes"],
    )

    # Prepare output directory
    output_dir = project_root / args.out
    html_index_path = (output_dir / "index.html").resolve()
    stlite_config_path = (output_dir / "stlite-config.json").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Move source files to output w/ hashes.
    print("Writing source files...", file=sys.stderr)
    file_urls = write_source_files(mounted_files, output_dir)

    # Config file so stlite loader can find the mounted files and entrypoint.
    print("Generating config...", file=sys.stderr)
    stlite_config_obj = get_stlite_config_file(
        entrypoint=app_path.relative_to(project_root).as_posix(),
        packages=config["packages"],
        file_urls=file_urls,
        output_dir=output_dir,
    )

    stlite_config = json.dumps(
        stlite_config_obj, ensure_ascii=False, separators=(",", ":")
    )
    stlite_config_path.write_text(stlite_config, encoding="utf-8")

    # Minimal HTML loader.
    print("Generating HTML loader...", file=sys.stderr)
    html_text = build_loader_html(
        title=config["title"],
        css_url=config["css_url"],
        js_url=config["js_url"],
    )

    html_index_path.write_text(html_text, encoding="utf-8")

    # Success message
    size_kb = len(html_text.encode("utf-8")) / 1024
    print("\nCompleted build, yo!")
    print(f"  Output: {html_index_path.relative_to(project_root)}")
    print(f"  Size: {size_kb:.1f} KB")
    print(f"  Files mounted: {len(mounted_files)}")
    print(f"  Directories scanned: {', '.join(config['mount_dirs'])}")
    print(f"  Pyodide packages: {', '.join(config['packages'])}")

    # Extract and display stlite version
    match = re.search(r"@stlite/mountable@([\d.]+)", config["js_url"])
    if match:
        print(f"  stlite version: {match.group(1)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
