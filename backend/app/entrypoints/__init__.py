"""One module per domain, each the entry point of a deployed function.

All nine share the shape around a different domain name; the shared part lives in
`app.composition.wiring`. None imports `app.main`, so one image cannot serve another.
"""
