"""Root B: one module per domain, each the entry point of a deployed function.

All nine are the same shape around a different domain name, and the repetition is
deliberate: an entrypoint is the file somebody opens when a function will not
start, and indirection there costs more than the duplication saves. Everything
they share lives in `app.composition.wiring`.

The import graph is the point. `app.entrypoints.media` reaches
`app.api.endpoints.images` and nothing else, so the media image imports no
`catalog` module, pays no `catalog` import at cold start, and cannot accidentally
serve a `catalog` route. `tests/entrypoints/` asserts exactly that, in fresh
interpreters, because a single module-scope import in the wiring would undo it
without failing anything else.

No entrypoint imports `app.main`. `app.main` is the whole-surface application the
monolith still serves, and an entrypoint that reached it would build all nine
domains at import and make the isolation accidental rather than structural.

`handler` here is Mangum, matching `app/lambda_handler.py`. The Lambda Web
Adapter switch is a later PR; these modules deploy nothing yet.
"""
