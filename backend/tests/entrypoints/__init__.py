"""Tests for the two composition roots.

Root A is `app.composition.app`, every domain in one process, and it is what
`app.main` serves. Root B is `app.entrypoints.<domain>`, one module per deployed
function. These tests are about the properties that make a cut safe: that the
two roots serve the same routes, that a Root B application imports only its own
domain, and that it does so with no AWS credentials at all.
"""
