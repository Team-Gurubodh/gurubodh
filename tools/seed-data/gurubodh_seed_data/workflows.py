from dataclasses import dataclass


@dataclass(frozen=True)
class SeedDataWorkflow:
    key: str
    status: str
    description: str


SUPPORTED_WORKFLOWS = (
    SeedDataWorkflow(
        key="glossary",
        status="scaffolded",
        description="Glossary seed data maintained through external spreadsheets.",
    ),
    SeedDataWorkflow(
        key="category",
        status="planned",
        description="Category seed data workflow to be added incrementally.",
    ),
    SeedDataWorkflow(
        key="subject",
        status="planned",
        description="Subject seed data workflow to be added incrementally.",
    ),
)


def list_workflows():
    return SUPPORTED_WORKFLOWS
