"""Exercise composed resource discovery from a non-editable installation."""

from contextlib import chdir
from importlib.metadata import distribution
import json
from pathlib import Path
import sys
import tempfile

from gurubodh.config import proofreading_config
from gurubodh.errors import ConfigurationError
from gurubodh.job_components import ComponentCatalog
from gurubodh.job_composition import resolve_job, resolve_lab_proofreading
from gurubodh.legacy.font_detection import load_approved_unicode_font_families
from gurubodh.project import resolve_project_context
from gurubodh.resource_discovery import bundled_resource_path


def main():
    project = Path(sys.argv[1]).resolve()
    module = Path(sys.modules["gurubodh"].__file__).resolve()
    package_distribution = distribution("gurubodh_cli")
    direct_url = json.loads(package_distribution.read_text("direct_url.json"))
    assert not direct_url.get("dir_info", {}).get("editable", False)

    def recorded(relative):
        parts = Path(relative).parts
        matches = [entry for entry in package_distribution.files or ()
                   if entry.parts[-len(parts):] == parts]
        if len(matches) == 1:
            return Path(package_distribution.locate_file(matches[0])).resolve()
        # ``pip --target`` flattens wheel data into the target and rewrites its
        # RECORD without the original ``.data`` entries. Normal prefix installs
        # retain those entries; the flattened layout is still a valid isolated
        # install and is anchored beside the imported package.
        flattened = module.parents[1] / relative
        assert not matches and flattened.is_file(), (relative, matches)
        return flattened.resolve()

    assert module == recorded("gurubodh/__init__.py"), module

    font_policy = bundled_resource_path("config/policies/source-fonts.json")
    assert font_policy == recorded("config/policies/source-fonts.json")
    assert bundled_resource_path("config/policies/source-fonts.schema.json") == recorded(
        "config/policies/source-fonts.schema.json"
    )
    policy = json.loads(font_policy.read_text(encoding="utf-8"))
    assert load_approved_unicode_font_families() == frozenset(
        " ".join(family.split()).casefold() for family in policy["approved_unicode_font_families"]
    )
    hidden_font_policy = font_policy.with_name(font_policy.name + ".hidden")
    font_policy.rename(hidden_font_policy)
    try:
        try:
            load_approved_unicode_font_families()
        except ConfigurationError as exc:
            assert "Source-font policy" in str(exc)
        else:
            raise AssertionError("missing packaged source-font policy did not fail")
    finally:
        hidden_font_policy.rename(font_policy)

    context = resolve_project_context(project)
    assert context.root == project
    assert context.resource_root != project
    assert (
        context.resource_root / "config/job-components/commands/prep-subject.json"
    ) == recorded("config/job-components/commands/prep-subject.json")
    assert context.legacy_converter == recorded("scripts/legacy_font_convert.js")
    assert context.legacy_converter == bundled_resource_path("scripts/legacy_font_convert.js")
    catalog = ComponentCatalog(context.root, context.resource_root)

    jobs = {}
    with tempfile.TemporaryDirectory(prefix="gurubodh-unrelated-cwd-") as directory:
        with chdir(Path(directory)):
            for command in ("prep-subject", "generate-chunks", "generate-docx"):
                resolved = resolve_job(
                    catalog,
                    command=command,
                    manifest_id="sub001_aps_example",
                    locale="hi-IN",
                    environment_id="development",
                    storage_profile_id="r2",
                    environ={},
                ).job
                assert resolved["source"]["backend"] == "r2"
                assert resolved["destination"]["backend"] == "r2"
                jobs[command] = resolved
    def selected_policy(command, kind):
        definition = catalog.load("command-definition", command).to_payload()
        identity = definition["default_profiles"][kind]
        return catalog.load(f"{kind}-profile", identity).to_payload()[kind]

    for command, kind in (("prep-subject", "proofreading"), ("generate-chunks", "chunking")):
        assert jobs[command][kind] == selected_policy(command, kind)
    lab = resolve_lab_proofreading(catalog)
    assert lab.settings.public_dict() == proofreading_config({
        "proofreading": selected_policy("lab-proofread", "proofreading")
    }).public_dict()

    # Discover every shipped profile; assert ownership and complete invocation
    # propagation without prescribing current IDs or relationships between them.
    for kind, command in (("proofreading", "prep-subject"), ("chunking", "generate-chunks")):
        directory = context.resource_root / f"config/job-components/profiles/{kind}"
        for path in sorted(directory.glob("*.json")):
            relative = path.relative_to(context.resource_root).as_posix()
            assert bundled_resource_path(relative) == recorded(relative)
            expected = catalog.load(f"{kind}-profile", path.stem).to_payload()[kind]
            resolved = resolve_job(
                catalog, command=command, manifest_id="sub001_aps_example",
                locale="hi-IN", environment_id="development", storage_profile_id="r2",
                environ={}, **{f"{kind}_profile_id": path.stem},
            ).job
            assert resolved[kind] == expected
            if kind == "proofreading":
                explicit_lab = resolve_lab_proofreading(catalog, proofreading_profile_id=path.stem)
                assert explicit_lab.settings.public_dict() == proofreading_config({
                    "proofreading": expected
                }).public_dict()

    lab_definition = catalog.load("command-definition", "lab-proofread").to_payload()
    profile_id = lab_definition["default_profiles"]["proofreading"]
    profile = context.resource_root / f"config/job-components/profiles/proofreading/{profile_id}.json"
    hidden = profile.with_name(profile.name + ".hidden")
    profile.rename(hidden)
    try:
        try:
            resolve_lab_proofreading(catalog)
        except ConfigurationError as exc:
            assert "resource is missing" in str(exc)
        else:
            raise AssertionError("missing packaged policy did not fail")
    finally:
        hidden.rename(profile)

    local_environment = {
        "GURUBODH_SOURCE_LIBRARY_ROOT": "/work/source",
        "GURUBODH_CMS_LIBRARY_ROOT": "/work/artifacts",
    }
    local = resolve_job(
        catalog,
        command="prep-subject",
        manifest_id="sub001_aps_example",
        locale="hi-IN",
        environment_id="development",
        storage_profile_id="local",
        environ=local_environment,
    ).job
    assert local["source"]["root_dir"] == "/work/source"
    assert local["destination"]["root_dir"] == "/work/artifacts"
    for command, variable, value in (
        ("prep-subject", "GURUBODH_SOURCE_LIBRARY_ROOT", "/work/source"),
        ("generate-chunks", "GURUBODH_CMS_LIBRARY_ROOT", "/work/artifacts"),
        ("generate-docx", "GURUBODH_CMS_LIBRARY_ROOT", "/work/artifacts"),
    ):
        mixed = resolve_job(
            catalog,
            command=command,
            manifest_id="sub001_aps_example",
            locale="hi-IN",
            environment_id="development",
            storage_profile_id="r2-output",
            environ={variable: value},
        ).job
        assert mixed["source"]["backend"] == "local"
        assert mixed["source"]["root_dir"] == value
        assert mixed["destination"]["backend"] == "r2"
    try:
        resolve_job(
            catalog,
            command="prep-subject",
            manifest_id="sub001_aps_example",
            locale="hi-IN",
            environment_id="development",
            storage_profile_id="local",
            environ={},
        )
    except ConfigurationError as exc:
        assert "GURUBODH_SOURCE_LIBRARY_ROOT" in str(exc)
    else:
        raise AssertionError("local composition accepted absent root bindings")
    print("Installed resource discovery and all three composed commands passed.")


if __name__ == "__main__":
    main()
