"""ATS provider registry.

Add a provider by dropping a module next to this file and listing it below.
Every module exposes fetch(slug) -> list[dict] in the shape described in base.py.
"""

from . import ashby, bamboohr, greenhouse, lever, personio, recruitee, smartrecruiters, workable

PROVIDERS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "workable": workable,
    "smartrecruiters": smartrecruiters,
    "recruitee": recruitee,
    "bamboohr": bamboohr,
    "personio": personio,
}


def get(name):
    try:
        return PROVIDERS[name]
    except KeyError:
        raise SystemExit(
            f"Unknown ATS provider '{name}'. Known: {', '.join(sorted(PROVIDERS))}"
        )
