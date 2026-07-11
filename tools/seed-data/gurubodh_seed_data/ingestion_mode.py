from dataclasses import dataclass


@dataclass(frozen=True)
class IngestionMode:
    apply: bool = False

    @property
    def name(self):
        return "apply" if self.apply else "dry-run"

    @property
    def can_write(self):
        return self.apply

    def require_write_allowed(self):
        if not self.can_write:
            raise RuntimeError("Dry-run mode cannot perform Strapi write requests.")
