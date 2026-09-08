"""What the two composition roots share.

`domains` names the nine domains and the routers each one owns. `wiring` holds
the `Domain` descriptor and `build_domain_app`, which is the one place the
middleware stack, the exception handlers, the CORS policy, the lifespan and the
five root routes are assembled. `app` is Root A, every domain in one process,
and it is what `app/main.py` serves; `app.entrypoints.<domain>` is Root B, one
module per deployed function.

Importing this package, or `app.composition.domains`, imports no endpoint module.
That is deliberate and it is tested: a domain's routers are reached only through
its descriptor's `load_routers` callable, so a process serving one domain never
imports the other eight.
"""
