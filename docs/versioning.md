# Versioning and releases

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
release_version=1.2.3       # replace with the version printed by make bump
git commit -am "Release v${release_version}"
git tag -a "v${release_version}" -m "v${release_version}"
git push --follow-tags
```

Pushing the tag triggers [`release.yml`](https://github.com/EpiForeSITE/epicc/blob/main/.github/workflows/release.yml), which publishes
the GitHub release with generated notes. The app's **What's new** link then points at it
with no further action. `make test` fails if `pyproject.toml` and `epicc.__version__`
ever disagree, and the release workflow refuses a tag that does not match the source.
