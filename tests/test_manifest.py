import textwrap

import pytest

from stello.errors import ManifestError
from stello.manifest import find_application, load_manifest
from stello.models import ArgType


def write_manifest(repo_root, body: str):
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "stello.yaml").write_text(textwrap.dedent(body))
    return repo_root


def test_valid_manifest_parses_and_coerces(tmp_path):
    repo = write_manifest(
        tmp_path,
        """
        applications:
          - name: model
            dir: ./apps/model
            script: ./src/model/main.py
            args:
              - name: scenario
                type: string
                default: base
              - name: retries
                type: int
                default: "3"
              - name: verbose
                type: bool
                default: false
          - name: webapp
            dir: ./apps/ui
            script: ./main.py
        """,
    )
    manifest = load_manifest(repo)
    assert [a.name for a in manifest.applications] == ["model", "webapp"]

    model = find_application(manifest, "model")
    scenario, retries, verbose = model.args
    assert scenario.default == "base" and scenario.type is ArgType.STRING
    assert retries.default == 3 and retries.type is ArgType.INT
    assert verbose.default is False and verbose.type is ArgType.BOOL

    # webapp has no args and defaults to an empty list
    assert find_application(manifest, "webapp").args == []
    assert find_application(manifest, "missing") is None


def test_descriptions_parse_at_all_levels(tmp_path):
    repo = write_manifest(
        tmp_path,
        """
        description: The team's shared models.
        applications:
          - name: model
            description: Forecasts revenue.
            dir: ./apps/model
            script: ./main.py
            args:
              - name: scenario
                description: Which scenario to run.
                default: base
        """,
    )
    manifest = load_manifest(repo)
    assert manifest.description == "The team's shared models."
    app = find_application(manifest, "model")
    assert app.description == "Forecasts revenue."
    assert app.args[0].description == "Which scenario to run."


def test_descriptions_are_optional(tmp_path):
    repo = write_manifest(
        tmp_path,
        """
        applications:
          - name: model
            dir: ./apps/model
            script: ./main.py
            args:
              - name: scenario
                default: base
        """,
    )
    manifest = load_manifest(repo)
    assert manifest.description is None
    app = find_application(manifest, "model")
    assert app.description is None
    assert app.args[0].description is None


def test_type_defaults_to_string(tmp_path):
    repo = write_manifest(
        tmp_path,
        """
        applications:
          - name: a
            dir: ./a
            script: ./m.py
            args:
              - name: label
                default: hello
        """,
    )
    (arg,) = load_manifest(repo).applications[0].args
    assert arg.type is ArgType.STRING and arg.default == "hello"


def test_resolved_paths(tmp_path):
    repo = write_manifest(
        tmp_path,
        """
        applications:
          - name: a
            dir: ./apps/a
            script: ./run.py
        """,
    )
    app = load_manifest(repo).applications[0]
    assert app.resolved_dir(repo) == (repo / "apps" / "a").resolve()
    assert app.resolved_script(repo) == (repo / "apps" / "a" / "run.py").resolve()


def test_missing_manifest_raises(tmp_path):
    with pytest.raises(ManifestError, match="No stello.yaml"):
        load_manifest(tmp_path)


def test_non_mapping_raises(tmp_path):
    repo = write_manifest(tmp_path, "- just a list\n")
    with pytest.raises(ManifestError, match="mapping"):
        load_manifest(repo)


def test_unknown_top_level_key_raises(tmp_path):
    repo = write_manifest(
        tmp_path,
        """
        applications: []
        surprise: true
        """,
    )
    with pytest.raises(ManifestError):
        load_manifest(repo)


@pytest.mark.parametrize("bad_dir", ["/etc", "../escape", "./apps/../../escape"])
def test_unsafe_dir_rejected(tmp_path, bad_dir):
    repo = write_manifest(
        tmp_path,
        f"""
        applications:
          - name: a
            dir: "{bad_dir}"
            script: ./m.py
        """,
    )
    with pytest.raises(ManifestError):
        load_manifest(repo)


def test_symlink_escape_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "link").symlink_to(outside, target_is_directory=True)
    (repo / "stello.yaml").write_text(
        textwrap.dedent(
            """
            applications:
              - name: a
                dir: ./link
                script: ./m.py
            """
        )
    )
    with pytest.raises(ManifestError, match="outside the project"):
        load_manifest(repo)


def test_bad_int_default_raises(tmp_path):
    repo = write_manifest(
        tmp_path,
        """
        applications:
          - name: a
            dir: ./a
            script: ./m.py
            args:
              - name: n
                type: int
                default: not-a-number
        """,
    )
    with pytest.raises(ManifestError):
        load_manifest(repo)


def test_bool_type_rejects_int_default(tmp_path):
    repo = write_manifest(
        tmp_path,
        """
        applications:
          - name: a
            dir: ./a
            script: ./m.py
            args:
              - name: flag
                type: bool
                default: 7
        """,
    )
    with pytest.raises(ManifestError):
        load_manifest(repo)


def test_missing_default_raises(tmp_path):
    repo = write_manifest(
        tmp_path,
        """
        applications:
          - name: a
            dir: ./a
            script: ./m.py
            args:
              - name: n
                type: int
        """,
    )
    with pytest.raises(ManifestError):
        load_manifest(repo)


def test_duplicate_application_names_raises(tmp_path):
    repo = write_manifest(
        tmp_path,
        """
        applications:
          - name: model
            dir: ./a
            script: ./m.py
          - name: model
            dir: ./b
            script: ./m.py
        """,
    )
    with pytest.raises(ManifestError, match="ambiguous application name"):
        load_manifest(repo)


def test_duplicate_arg_names_raises(tmp_path):
    repo = write_manifest(
        tmp_path,
        """
        applications:
          - name: a
            dir: ./a
            script: ./m.py
            args:
              - name: x
                default: "1"
              - name: x
                default: "2"
        """,
    )
    with pytest.raises(ManifestError, match="duplicate argument"):
        load_manifest(repo)
