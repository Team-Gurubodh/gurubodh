"""Check declared dependencies and actual imports in independent interpreters."""

import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


CLI_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = CLI_ROOT / "gurubodh"
# Discover files without importing parent packages (pkgutil.walk_packages would
# initialize them and could hide the very import-order defect we are checking).
MODULES = {
    ".".join(path.relative_to(CLI_ROOT).with_suffix("").parts).removesuffix(".__init__"): path
    for path in sorted(PACKAGE.rglob("*.py"))
}
COMMANDS = (
    "gurubodh.__main__", "gurubodh.cli", "gurubodh.pipelines",
    "gurubodh.prep_subject_checkpoints", "gurubodh.ml.tokenization.cli",
    *(name for name in MODULES if name.startswith("gurubodh.lab")),
)
CHUNK_IMPLEMENTATION = (
    "gurubodh.ml.embeddings", "gurubodh.ml.semantic_chunking.chunker",
    "gurubodh.ml.semantic_chunking.segmenter",
)
PROVIDERS = (
    "boto3", "botocore", "google.genai", "openai", "sentence_transformers",
    "transformers", "torch", "huggingface_hub",
)


def matches(name, prefixes):
    return any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)


def forbidden_dependencies(module):
    forbidden = []
    if module not in {"gurubodh.__main__", "gurubodh.cli"}:
        forbidden.append("gurubodh.cli")
    if not matches(module, COMMANDS):
        forbidden.extend(COMMANDS)
    if module in {"gurubodh.ml.embeddings", "gurubodh.ml.errors"}:
        forbidden.append("gurubodh.ml.semantic_chunking")
    if module in {
        "gurubodh.ml.semantic_chunking", "gurubodh.ml.semantic_chunking.config",
        "gurubodh.ml.semantic_chunking.models",
    }:
        forbidden.extend(CHUNK_IMPLEMENTATION)
    if module == "gurubodh.contracts":
        forbidden.extend(name for name in MODULES if name not in {"gurubodh", module})
    return tuple(forbidden)


def declared_imports(source, module, is_package=False):
    """Resolve absolute/relative imports, retaining type and deferred context."""
    package = module if is_package else module.rpartition(".")[0]

    def walk(node, kind="runtime"):
        if isinstance(node, ast.If) and (
            isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"
            or isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING"
        ):
            for child in node.body:
                yield from walk(child, "type-only")
            for child in node.orelse:
                yield from walk(child, kind)
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and kind != "type-only":
            kind = "compatibility" if node.name == "__getattr__" else "deferred"
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, kind, node.lineno
        elif isinstance(node, ast.ImportFrom):
            target = node.module or ""
            if node.level:
                target = importlib.util.resolve_name("." * node.level + target, package)
            yield target, kind, node.lineno
            for alias in node.names:
                # `from gurubodh import cli` names a module; most imported names
                # are classes/functions, not additional dependency edges.
                child = target + "." + alias.name
                if child in MODULES:
                    yield child, kind, node.lineno
        for child in ast.iter_child_nodes(node):
            yield from walk(child, kind)

    return list(walk(ast.parse(source)))


IMPORT_PROBE = r'''
import importlib
import importlib.abc
import json
import sys

module, forbidden, extra = json.loads(sys.argv[1])
attempted = []

def matches(name):
    return any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)

class ImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if matches(fullname):
            attempted.append(fullname)
            raise AssertionError(f"{module} attempted forbidden import {fullname}")

def audit(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn"}:
        attempted.append(event)
        raise AssertionError(f"Import attempted external operation: {event}")

def profile(frame, event, arg):
    if event == "call" and frame.f_globals.get("__name__", "").startswith("gurubodh."):
        name = frame.f_code.co_name
        if name == "main" or name.startswith("run_"):
            attempted.append(name)
            raise AssertionError(f"Import executed workflow: {name}")

assert not any(name == "gurubodh" or name.startswith("gurubodh.") for name in sys.modules)
sys.meta_path.insert(0, ImportGuard())
sys.addaudithook(audit)
sys.setprofile(profile)
importlib.import_module(module)
exec(extra)
sys.setprofile(None)
assert not attempted, attempted  # Even a caught import/operation failure is a violation.
assert not any(matches(name) for name in sys.modules), sorted(filter(matches, sys.modules))
print("import-probe-complete")
'''


class ImportBoundaryTests(unittest.TestCase):
    def probe(self, module, *, forbidden=None, extra=""):
        if forbidden is None:
            forbidden = forbidden_dependencies(module)
        result = subprocess.run(
            [sys.executable, "-B", "-c", IMPORT_PROBE,
             json.dumps([module, (*PROVIDERS, *forbidden), extra])],
            cwd=CLI_ROOT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "HF_HUB_OFFLINE": "1"},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, f"{module}\n{result.stdout}\n{result.stderr}")
        self.assertEqual(result.stdout, "import-probe-complete\n", f"{module}: import did not complete quietly")

    def test_every_package_module_imports_independently_without_side_effects(self):
        for module in MODULES:
            with self.subTest(module=module):
                self.probe(module)

    def test_declared_dependencies_respect_ownership_including_deferred_imports(self):
        for module, path in MODULES.items():
            for target, kind, line in declared_imports(
                path.read_text(encoding="utf-8"), module, path.name == "__init__.py",
            ):
                # Contracts' type references and deliberate lazy package exports
                # are not eager loads. Their actual loading is checked by probes.
                if module == "gurubodh.contracts" and kind == "type-only":
                    continue
                if module == "gurubodh.ml.semantic_chunking" and kind == "compatibility":
                    forbidden = COMMANDS
                else:
                    forbidden = forbidden_dependencies(module)
                with self.subTest(module=module, line=line, kind=kind, target=target):
                    self.assertFalse(matches(target, forbidden))

    def test_import_scan_distinguishes_relative_type_and_compatibility_imports(self):
        source = """
from . import cli
if TYPE_CHECKING:
    from .proofreading.settings import ProofreadingSettings
def __getattr__(name):
    from .ml.semantic_chunking import SemanticChunker
def run():
    import gurubodh.lab_docx
"""
        imports = {(target, kind) for target, kind, _ in declared_imports(source, "gurubodh.example")}
        self.assertIn(("gurubodh.cli", "runtime"), imports)
        self.assertIn(("gurubodh.proofreading.settings", "type-only"), imports)
        self.assertIn(("gurubodh.ml.semantic_chunking", "compatibility"), imports)
        self.assertIn(("gurubodh.lab_docx", "deferred"), imports)

    def test_package_exports_preserve_identity_and_lazy_loading(self):
        exports = {
            "Chunk": "models", "ChunkedDocument": "models",
            "SemanticChunkConfig": "config", "SemanticChunker": "chunker",
            "ParagraphSegmenter": "segmenter",
            "SemanticChunkingParagraphSegmenter": "segmenter",
        }
        for name, component in exports.items():
            with self.subTest(name=name):
                self.probe(
                    "gurubodh.ml.semantic_chunking",
                    forbidden=CHUNK_IMPLEMENTATION if component in {"models", "config"} else (),
                    extra=f"""
from gurubodh.ml.semantic_chunking import {name} as exported
from gurubodh.ml.semantic_chunking.{component} import {name} as direct
assert exported is direct
""",
                )
        self.probe("gurubodh.ml.semantic_chunking", forbidden=(), extra=f"""
import gurubodh.ml.semantic_chunking as package
from gurubodh.ml.semantic_chunking import *
assert set(package.__all__) == {set(exports)!r}
assert all(globals()[name] is getattr(package, name) for name in package.__all__)
assert not hasattr(package, 'unknown_export')
""")

    def test_exception_identity_is_compatible_in_both_import_orders(self):
        for first in ("gurubodh.ml.embeddings", "gurubodh.ml.semantic_chunking.config"):
            with self.subTest(first=first):
                self.probe(first, forbidden=(), extra="""
from gurubodh.ml.errors import ModelCacheConfigError
from gurubodh.ml.embeddings import ModelCacheConfigError as embedding_error
from gurubodh.ml.semantic_chunking.config import ModelCacheConfigError as config_error
assert ModelCacheConfigError is embedding_error is config_error
assert issubclass(ModelCacheConfigError, RuntimeError)
""")


if __name__ == "__main__":
    unittest.main()
