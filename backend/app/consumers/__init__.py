"""Root C: the stream consumers, one module per seam that inverts a write.

Roots A and B in `app/composition/` both build a FastAPI application. This one
does not. A stream consumer is a Lambda handler invoked by an event source
mapping with a batch of DynamoDB stream records, and there is no request, no
router and no middleware anywhere in it.

Splitting it out rather than adding a route to a domain is the whole point of
the seam. Section 1.3 of `docs/migration/split-plan.md` names the vote
denormalisation as the one cross-domain write in the application that is not a
delete: `moderation` owns `votes` and writes `parts`, which `catalog` owns.
Inverting it means `catalog` reads the `votes` stream and writes its own table,
so `moderation` is left with no cross-domain write at all.

**These modules import no endpoint module and no router.** They reach the
repositories through the same registry the domain bundles use, so the import
graph of a consumer image is the data layer and nothing else. That is what
`tests/consumers/` asserts.
"""
