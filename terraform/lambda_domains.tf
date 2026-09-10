# ---------------------------------------------------------------------------
# The per-domain FastAPI functions, delivered as container images and run under
# the AWS Lambda Web Adapter. Section 3.3 and section 3.4 of
# docs/migration/split-plan.md, row 13 of section 8.
#
# `media` from row 13, `build-logs` from row 18, `moderation` from row 19,
# `vehicles` from row 20, `admin` from row 21, `build-lists` from row 26,
# `identity` from row 27, `catalog` from row 29 and `users` from row 31 are the
# entries, and with row 31 that is all nine. The map is complete: no later row
# adds a domain, and the shape here is what made each of the nine one entry in
# `local.lambda_domains`, with the module call, the IAM policy and the outputs
# all keying off it, so adding a domain was adding a map entry.
#
# The monolith in lambda.tf is deliberately untouched. It still serves every
# route this file has not cut away from it, because a function here is only
# reached once apigateway.tf names its prefixes. That is what keeps each row
# additive and its rollback a matter of deleting the route entry again.
#
# Every AWS_LWA_* setting is baked into the image by backend/Dockerfile
# (AWS_LWA_PORT, AWS_LWA_READINESS_CHECK_PATH, AWS_LWA_READINESS_CHECK_PROTOCOL
# and AWS_LWA_ASYNC_INIT), and so is PORT, and so is RUN_STARTUP_TASKS. None is
# repeated here. Repeating one would put two sources of truth on the same
# setting and let them drift, and PORT is the one where drift is fatal rather
# than untidy: the monolith's environment sets PORT=8000 while the image binds
# and polls 8080, so copying the monolith's map wholesale would present as a
# readiness check that never passes with no application logs to say why.
# ---------------------------------------------------------------------------

locals {
  # One entry per domain whose function this environment declares. The gate
  # below turns this into local.lambda_domains, which is what everything else
  # reads: in a fresh account with no images yet the gate resolves it to empty.
  # The keys are names from
  # `local.lambda_domain_names` in ecr.tf, which is what ties a function to its
  # ECR repository and to the deploy role's grant.
  #
  # `secrets` is whether the function reads the carmodpicker-<env>/app secret at
  # all; `tables` names the tables it writes and `read_tables` the ones it only
  # reads, both as keys of module.dynamodb, so every ARN comes out of the module
  # rather than being rebuilt by hand and a renamed table is a plan error rather
  # than a runtime denial.
  #
  # How `media`'s two table lists were derived, from the code rather than from
  # the plan's ownership column:
  #
  #   - `app/composition/domains.py` declares `_MEDIA_REPOSITORIES` as `users`,
  #     `car_generations`, `parts`, `build_lists` and `image_source_mappings`.
  #     `app/db/dynamo/registry.py`'s `tables_for` maps each of those five
  #     repository names to a table suffix, and for `media` the mapping is the
  #     identity: the five repositories are the five tables.
  #     `backend/tests/entrypoints/test_repository_bundles.py` recomputes that
  #     tuple from the real import graph and fails if it drifts, so the bundle is
  #     the checked statement of what this function can reach.
  #   - Of the five, only `image_source_mappings` is written.
  #     `app/api/endpoints/images.py` calls `repos.image_source_mappings.record`
  #     and `.get_by_source_url`, and reaches the other four through `.get` and
  #     through `app/api/utils/bucket_orphan_utils.py`'s orphan sweep, which is
  #     five full reads to find unreferenced S3 objects. Section 1.2's ownership
  #     table agrees: `image_source_mappings` is owned by `media` and written by
  #     nothing else, and `media` appears in no other row's "also written today
  #     by" column. So `media` is the one domain whose write set needs no seam
  #     unwound before it is cut, which is part of why it is cut first.
  #   - `rate-limits` is in `tables` and is not in either of those lists. It is
  #     the shared limiter's counter table, layer 2 of the rate limiting
  #     standard, and it is reached from the middleware stack rather than from a
  #     repository, so `_MEDIA_REPOSITORIES` cannot name it. Every one of the
  #     nine gets it, for the reason locals in lambda.tf already records: the
  #     per-domain split replaces the monolith's wildcard with per-function
  #     policies, and at that point every domain needs the limiter grant. The
  #     limiter fails open, so withholding it would not break the function; it
  #     would silently turn layer 2 off for this domain and log a warning on
  #     every request, which is worse than a denial because nothing fails.
  #
  # `ses` is whether the function may send transactional mail, and it carries
  # both the `ses:SendEmail` grant and the EMAIL_FROM and EMAIL_ENABLED pair,
  # because `app/core/email.py` needs all three before a send is anything but a
  # debug log. Row 27 sets it on `identity` and it is false on every other
  # entry; section 3.4's other half went to the price alert stream consumer
  # rather than to the `admin` function, for the reason recorded there.
  #
  # `s3` is whether the function gets the user images bucket at all, and
  # `s3_delete_only` narrows what it gets when it does. Section 3.4 named
  # `media` and `users`, and with row 31 both are here: the full set including
  # ListBucket for `media` and the three object actions for avatars for
  # `users`, whose upload route puts and deletes on the same request.
  #
  # Row 26 found a third. `build-lists` deletes gallery images, which section
  # 3.4 did not anticipate because it reasoned from the two domains whose names
  # are about images rather than from the calls. The correction is in the code's
  # favour and is narrowing rather than widening: `s3_delete_only` grants
  # `s3:DeleteObject` and `s3:ListBucket` and withholds `s3:PutObject` and
  # `s3:GetObject`, which is the whole of what the one call needs. The
  # derivation for `build-lists` below names that call.
  #
  # How `build-logs`'s two table lists were derived, by row 18 and by the same
  # method as `media`'s above, from the code rather than from the ownership
  # column:
  #
  #   - `app/composition/domains.py` declares `_BUILD_LOGS_REPOSITORIES` as
  #     `users`, `build_lists`, `build_logs` and `build_log_posts`, and
  #     `app/db/dynamo/registry.py`'s `tables_for` maps each of those four to a
  #     table suffix of the same name, so the four repositories are four tables.
  #     `backend/tests/entrypoints/test_repository_bundles.py` recomputes that
  #     tuple from the real import graph, so the bundle is a checked statement
  #     of what this function can reach.
  #   - Of the four, only `build_log_posts` is written. The domain has five
  #     routes and `app/api/endpoints/build_logs.py` calls `.create`, `.update`
  #     and `.delete` on `repos.build_log_posts` alone; `build_logs`,
  #     `build_lists` and `users` are reached through `.get`, `.get_many`,
  #     `.for_build_list`, `.all_for_build_log` and `.count`, every one a read.
  #   - `build_logs` is in `read_tables` even though section 1.2 gives this
  #     domain ownership of it, and that is deliberate rather than an oversight.
  #     Ownership is about who may write a table, not about who does today, and
  #     nothing in this domain's own five routes writes it: the thread row is
  #     created by `app/api/services/build_list_service.py` when a build list is
  #     created and deleted by `build_log_delete_actions` in the same cascade,
  #     both of which run in `build-lists` and are seam work for row 26. Until
  #     that seam moves, granting this function write on `build_logs` would
  #     grant an action no code path here takes, which is the opposite of what
  #     a per-domain split is for. Row 26 is where the grant follows the writer.
  #   - `rate-limits` is in `tables` for the reason `media`'s entry above
  #     records: it is the shared limiter's counter table, reached from the
  #     middleware stack rather than from a repository, so the bundle cannot
  #     name it, and the limiter fails open, so withholding it would silently
  #     turn layer 2 off for this domain rather than failing.
  #
  # 256 MB rather than `media`'s 512. `media` is sized for Pillow decoding
  # uploaded images in memory; this domain serves five JSON routes over
  # DynamoDB with no image handling and no native work, so it takes the smaller
  # size. It is also the cheapest thing to raise if the cold start or the
  # duration says otherwise, since memory is the only tuning knob on a function
  # this simple.
  # How `moderation`'s two table lists were derived, by row 19 and by the same
  # method as the two above, from the code rather than from the ownership
  # column:
  #
  #   - `app/composition/domains.py` declares `_MODERATION_REPOSITORIES` as
  #     `users`, `car_makes`, `car_models`, `car_generations`, `parts`,
  #     `build_lists`, `votes`, `reports` and `bug_reports`, and
  #     `app/db/dynamo/registry.py`'s `tables_for` maps each of those nine to a
  #     table suffix of the same name.
  #     `backend/tests/entrypoints/test_repository_bundles.py` recomputes that
  #     tuple from the real import graph, so the bundle is a checked statement
  #     of what this function can reach.
  #   - Nine repositories, seven tables granted. `car_makes` and `car_models`
  #     are in the bundle and in neither list here, and that is the gap between
  #     what the import graph reaches and what a code path calls. The bundle
  #     test computes reachability through imports, and those two arrive with
  #     the catalogue types the vote and report schemas name; no route, service
  #     or utility under this domain calls `repos.car_makes` or
  #     `repos.car_models` at all. Granting a table on the strength of an import
  #     rather than a call would hand this function two tables no request can
  #     touch, which is the opposite of what a per-domain split is for.
  #   - Four tables are written. `app/api/services/vote_service.py` calls
  #     `.create`, `.update` and `.delete` on `repos.votes`;
  #     `app/api/services/report_service.py` calls `.create`, `.update` and
  #     `.delete` on `repos.reports`; and
  #     `app/api/services/bug_report_service.py` calls `.create`, `.update` and
  #     `.delete` on `repos.bug_reports`. Those three are the domain's own, per
  #     section 1.2.
  #   - There was a fourth written table until row 24, and its removal is the
  #     visible half of that row. `vote_service._sync_part_net_votes` used to
  #     call `self.repos.parts.update(str(entity_id), net_votes=upvotes -
  #     downvotes)` after every vote create, update and remove on a part, which
  #     is seam 3 of section 1.3: the one cross-domain write in the application
  #     that was not a delete. Row 24 inverted it. The vote path now writes only
  #     `votes`, the votes stream carries the change to
  #     `carmodpicker-<env>-catalog-votes-consumer` in
  #     lambda_stream_consumers.tf, and that function recomputes the aggregate
  #     and writes the part. So `parts` moved from `tables` to `read_tables`
  #     here, which is the narrowing this comment used to promise.
  #
  #     The two halves have to land in the same apply. Removing the grant before
  #     the consumer exists leaves `net_votes` with nothing writing it; adding
  #     the consumer before removing the grant leaves two writers racing on the
  #     same attribute. Terraform applies both from this one configuration, so
  #     the only way to get one without the other is to split them across
  #     commits, which is why they are not split.
  #   - Three tables are read only. `users` for the reporter and the author
  #     (`repos.users.get` and `.get_many` in `report_service`), and
  #     `build_lists`, `car_generations` and `parts` for the vote and report
  #     targets, which are polymorphic over `entity_type`: `_get_entities`
  #     dispatches to `repos.build_lists.get_many`,
  #     `repos.car_generations.get_many` or `repos.parts.get_many`. `parts` sat
  #     in `tables` rather than `read_tables` until row 24, because a table
  #     appears in exactly one of the two lists and the write set was the wider
  #     grant it then needed. With the write gone it takes the narrower list,
  #     which is where the read path alone belongs.
  #   - `rate-limits` is in `tables` for the reason both entries above record:
  #     it is the shared limiter's counter table, reached from the middleware
  #     stack rather than from a repository, so the bundle cannot name it, and
  #     the limiter fails open, so withholding it would silently turn layer 2
  #     off for this domain rather than failing.
  #
  # 256 MB, the same as `build-logs` and for the same reason. This domain's
  # twenty routes are JSON over DynamoDB: no Pillow, no image decoding and no
  # native work anywhere in `votes.py`, `reports.py`, `bug_reports.py` or their
  # three services, which import nothing beyond FastAPI, the schemas and the
  # repositories. Only `media` needs 512.
  #
  # How `vehicles`' two table lists were derived, by row 20 and by the same
  # method as the three above. This is the entry the whole least-privilege claim
  # rests on, because it is the only one of the nine whose write list holds
  # nothing but the limiter's own table and whose `secrets` is false:
  #
  #   - `app/composition/domains.py` declares `_VEHICLES_REPOSITORIES` as
  #     `_CATALOG_REPOSITORIES + ("build_lists",)`, which is sixteen
  #     repositories: `users`, the three car tables, `categories`,
  #     `part_manufacturers`, `retailers`, `parts`, `part_cars`,
  #     `part_listings`, `part_price_history`, `part_price_alerts`,
  #     `build_list_parts`, `votes`, `reports` and `build_lists`.
  #     `backend/tests/entrypoints/test_repository_bundles.py` recomputes that
  #     tuple from the real import graph, so the bundle is a checked statement
  #     of what this function can reach.
  #   - Sixteen repositories, seven tables granted, and every one of the seven is
  #     a read. The gap is the same one row 19 recorded and it is wider here than
  #     it has been on any cut so far, for one reason: `search.py` constructs a
  #     `PartService`, so the whole of that module's import graph is reachable,
  #     while the only method this domain calls on it is `search_parts`. The nine
  #     ungranted repositories are `categories`, `retailers`, `part_cars`,
  #     `part_listings`, `part_price_history`, `part_price_alerts`,
  #     `build_list_parts`, `votes` and `reports`. They are reached only from
  #     `PartService` methods no vehicles route calls, chiefly the part purge and
  #     the price capture, and from the catalogue schemas. Granting a table on
  #     the strength of an import rather than a call would hand this function
  #     nine tables no request can touch.
  #   - No table is written, which is what makes this entry different in kind
  #     from the three above rather than merely smaller. Both routers are read
  #     only by construction: `car_generations.py` builds its
  #     `BaseDynamoEndpointRouter` with `disable_endpoints = ["create",
  #     "update", "delete"]`, so the generated writing routes are never
  #     registered, and the seven hand-written routes above it are all `GET`.
  #     `search.py` is one `GET`. `car_generation_service.py` calls no `.create`,
  #     `.update` or `.delete` on any repository, and neither does the
  #     `search_parts` path.
  #   - The seed is the one write this domain owns and it does not run here.
  #     `vehicles` is the only descriptor setting `seeds`, and
  #     `app/composition/wiring.py` gates `init_car_generations()` on
  #     `settings.RUN_STARTUP_TASKS`, which `backend/Dockerfile` bakes to
  #     `false` and which `local.lambda_domain_environment` deliberately does not
  #     set. The entrypoint is Mangum with `lifespan="off"` besides, so the
  #     lifespan that would call it never runs. Section 7 already says the seed
  #     needs an owner and belongs behind an explicit admin route or a one-off
  #     job; `admin/db_ops` has the equivalent endpoint and row 21 is where that
  #     grant lands. Granting the three car tables write here to cover a seed
  #     that cannot fire would give away the least-privilege claim for nothing.
  #   - Seven tables are read. `car_generations`, `car_models` and `car_makes`
  #     are the domain's own three, per section 1.2: `car_generations.py` calls
  #     `repos.car_makes.count()` and `repos.car_models.count()` directly, and
  #     `car_generation_service._models_and_makes` calls
  #     `repos.car_models.get_many` and `repos.car_makes.get_many` on every
  #     hydrate, so all three are called rather than merely imported.
  #   - The other four are seam 5, the search fan-out section 1.3 leaves
  #     synchronous. `search.py` reads `build_lists` through
  #     `search.scan_matching(repos.build_lists, ...)`, `users` through
  #     `repos.users.search`, and `parts` and `part_manufacturers` through
  #     `PartService.search_parts`, which scans `repos.parts` and lists
  #     `repos.part_manufacturers`. Cross-domain reads are allowed with
  #     read-only IAM and that is the whole of what this domain does with them.
  #   - `rate-limits` is in `tables` for the reason all three entries above
  #     record: it is the shared limiter's counter table, reached from the
  #     middleware stack rather than from a repository, so the bundle cannot name
  #     it. It is a genuine write, `update_item` and `put_item` in
  #     `shared_rate_limiter.py`, which is why this domain has a `tables` list at
  #     all rather than an empty one. The limiter fails open, so withholding it
  #     would silently turn layer 2 off for this domain rather than failing.
  #   - `secrets` is false, and this is the only entry where it is. Section 3.4
  #     calls `vehicles` the cheapest proof that the IAM split is real: every
  #     route under both prefixes is a public read, `allow_public_read = true`
  #     keeps `get_current_user` off the generated routes, and the descriptor
  #     sets no `requires_secrets`, so nothing in this function reads
  #     `SECRET_KEY`. The runtime policy therefore carries no
  #     `secretsmanager:GetSecretValue` statement and
  #     `local.lambda_domain_environment` sets no `APP_SECRETS_ARN`. This is only
  #     possible because section 2.3's lazy secret resolution landed; before it,
  #     importing `app.core.config` called Secrets Manager and every function
  #     needed the grant whether it used a secret or not.
  #
  # 256 MB, the same as `build-logs` and `moderation`. Eleven read-only JSON
  # routes over DynamoDB with no Pillow and no native work. Search is the one
  # route worth a second thought, because `scan_matching` pages full table scans
  # of `build_lists`, `users` and `parts` and holds the matches in memory, but it
  # is bounded by `DYNAMODB_SEARCH_SCAN_PAGE_LIMIT` and holds parsed models
  # rather than images. Memory is the cheapest knob to raise if the duration says
  # otherwise. Only `media` needs 512.
  #
  # How `admin`'s two table lists were derived, by row 21 and by the same method
  # as the four above. This is the mirror image of `vehicles`: that entry writes
  # nothing but the limiter's table, and this one writes fourteen tables across
  # six domains. Both are the same rule applied honestly, which is that the
  # grant follows the call:
  #
  #   - `app/composition/domains.py` declares `_ADMIN_REPOSITORIES` as
  #     twenty-one repositories, the second widest bundle after the monolith's
  #     twenty-five. `app/db/dynamo/registry.py`'s `tables_for` maps each of the
  #     twenty-one to a table suffix of the same name, so twenty-one
  #     repositories are twenty-one tables, and
  #     `backend/tests/entrypoints/test_repository_bundles.py` recomputes that
  #     tuple from the real import graph, so the bundle is a checked statement
  #     of what this function can reach.
  #   - Twenty-one in the bundle, twenty granted. The one ungranted repository
  #     is `retailers`, and it is the whole of the bundle-to-grant gap on this
  #     cut, which makes this the narrowest gap of the five. `retailers` is
  #     reached twice and neither reach is an admin route:
  #     `part_price_alert_service.evaluate_alerts_for_listing` calls
  #     `repos.retailers.get` for the email body, and that function is invoked
  #     only from `part_listing_service.create_or_update_listing_and_price`,
  #     which is `catalog`'s price capture and not served here; and
  #     `PartService`'s create and update paths call `repos.retailers.get`, and
  #     the only `PartService` method any admin route calls is `purge`.
  #     Granting a table on the strength of an import rather than a call is what
  #     the four entries above refused, and refusing it here as well is the only
  #     thing that keeps the wide write list below honest.
  #   - Fourteen tables are written, and every one has a named caller.
  #     `part_price_alerts` is the domain's own, per section 1.2:
  #     `part_price_alert_service` calls `.create` and `.update` from subscribe,
  #     patch, delete and the token unsubscribe, and
  #     `part_service.purge_related_rows_for_parts` calls `.delete_for_parts`.
  #     The other thirteen are `admin/db_ops`, which is four routes that seed
  #     and purge:
  #       * `POST /admin/db-ops/init/car-generations` calls
  #         `app/core/init_cars.py`'s `init_car_generations`, which calls
  #         `.create_unique` and `.update_unique` on `car_makes`, `car_models`
  #         and `car_generations`. This is the seed row 20 could not run and
  #         deliberately did not grant: `vehicles` is the descriptor that sets
  #         `seeds`, `run_startup_tasks` is gated on `RUN_STARTUP_TASKS`, which
  #         `backend/Dockerfile` bakes to `false`, and the entrypoint is Mangum
  #         with `lifespan="off"`, so the lifespan that would call it never
  #         runs there. Here it is an explicit `POST` behind
  #         `get_current_admin_user`, which is exactly the owner section 7 said
  #         the seed needed, so the write grant lands with the route rather
  #         than with the table's owner.
  #       * `POST /admin/db-ops/init/part-categories` calls
  #         `app/core/init_categories.py`, which calls `.create_unique` and
  #         `.update_unique` on `categories`.
  #       * `POST /admin/db-ops/cars/delete-all` calls `.update` on
  #         `build_lists` to null out `car_id`, `.delete_for_entity_type` on
  #         `votes`, `.delete_for_car` on `part_cars` and `.delete_unique` on
  #         all three car tables.
  #       * `POST /admin/db-ops/parts/delete-all` and
  #         `POST /admin/db-ops/part-manufacturers/delete-all` run the part
  #         purge, which is the widest single path in the application:
  #         `PartService.purge` calls `delete_part_listings`, which calls
  #         `.delete_for_part` on `part_listings` and `.delete_for_listing` on
  #         `part_price_history`, then `.save_unique` or `.put` on `parts` to
  #         unlink duplicates, `.unlink_action` on `part_cars` and
  #         `.delete_unique` on `parts`; and `purge_related_rows_for_parts`
  #         calls `.delete_for_entities` on `votes` and `reports`,
  #         `.batch_delete` on `build_list_parts` and `.delete_for_parts` on
  #         `part_price_alerts`. The manufacturer route additionally calls
  #         `.update_unique` on `parts` and `.delete_unique` on
  #         `part_manufacturers`.
  #     Section 1.2's "also written today by" column names `admin` against
  #     `parts`, `part_cars`, `part_manufacturers`, `categories`, the three car
  #     tables, `build_lists` and `votes`, and every one of those is here.
  #     `part_listings`, `part_price_history`, `build_list_parts` and `reports`
  #     are here too and the column credits them to `catalog` and `users`
  #     instead, which is the column being about the domain that owns the seam
  #     rather than about every caller: the purge is one code path and it is
  #     reached from `catalog` and from here.
  #
  #     Section 1.3's seams 1, 2 and 4 are what narrow this list, and rows 25,
  #     28 and 30 are where they land. Row 28 has landed and took
  #     `build_list_parts` with it, per the note on the `tables` list below.
  #     `part_listings`, `part_price_history` and `reports` stayed, because the
  #     purge was not their only caller. Seams 1 and 4 are still outstanding,
  #     and until they land the grant follows the writer, and the writer is
  #     this function.
  #   - Six tables are read only. `users` is read on eleven of the twelve routes
  #     before the handler runs: `get_current_user` and `get_current_admin_user`
  #     both call `repos.users.get_by_username` to resolve the token subject.
  #     `oauth_accounts`, `webauthn_credentials`, `build_list_phases`,
  #     `build_logs` and `image_source_mappings` are `admin/stats`, whose one
  #     route calls `.count()` on each and `scan_all()` on `build_list_phases`.
  #     Nothing writes any of the six. `part_listings`, `part_price_history`,
  #     `part_cars`, `votes` and `reports` are also counted by that route and
  #     are in `tables` rather than here, because a table appears in exactly one
  #     of the two lists and the write set is the wider grant; the twelve write
  #     actions include the five read ones.
  #   - `rate-limits` is in `tables` for the reason all four entries above
  #     record: it is the shared limiter's counter table, reached from the
  #     middleware stack rather than from a repository, so the bundle cannot
  #     name it, and the limiter fails open, so withholding it would silently
  #     turn layer 2 off for this domain rather than failing.
  #   - `secrets` is true, and back to true after `vehicles`. Eleven of the
  #     twelve routes verify a token and the twelfth, the price-alert
  #     unsubscribe, decodes one of its own, so `SECRET_KEY` is read on every
  #     request; the descriptor sets `requires_secrets=("SECRET_KEY",)` to say
  #     so. The runtime policy therefore carries `secretsmanager:GetSecretValue`
  #     and `local.lambda_domain_environment` sets `APP_SECRETS_ARN`.
  #   - `s3` is false. `crawled_pages` is the one route that might have wanted a
  #     bucket and it does not: it parses HTML the Chrome extension posts in the
  #     request body and returns the result, touching no repository and no
  #     object store. The `crawl-data` bucket in s3.tf is not read by any route
  #     in this domain.
  #   - SES is not granted here and no `EMAIL_FROM` is set, which the file
  #     header's list of omitted environment keys anticipates but gets slightly
  #     wrong for today. Section 3.4 gives `ses:SendEmail` to `identity` and
  #     `admin`, and `admin`'s half of that is the price-drop alert email. That
  #     email is sent from `evaluate_alerts_for_listing`, which is called only
  #     from `part_listing_service.create_or_update_listing_and_price`, which is
  #     `catalog`'s price capture and runs on the monolith today. No route this
  #     function serves sends mail, so a sender address and a send grant here
  #     would both be configuration for a code path that cannot execute. Row 25
  #     is seam 4, which moves the email onto an `admin` stream handler, and
  #     that is the row where the grant and the environment key arrive together
  #     with the code that uses them.
  #
  # 256 MB, the same as `build-logs`, `moderation` and `vehicles`. Twelve JSON
  # routes over DynamoDB with no Pillow and no native work anywhere in the four
  # modules. The delete-all routes are the ones worth a second thought, because
  # `repos.parts.list_all()` and `repos.build_lists.scan_all()` hold whole tables
  # in memory and the purge then walks them one at a time, but the binding
  # constraint there is the 29 second timeout rather than the memory: section 7's
  # open question 6 already says a full-table admin operation behind an HTTP
  # route will time out as the tables grow, and the fix for that is a job rather
  # than a larger function. Raising memory would buy CPU and so a little wall
  # clock, and it is the cheapest knob if the duration says so, but it is not the
  # answer to that question and this row does not pretend it is.
  #
  # How `build-lists`' two table lists were derived, by row 26 and by the same
  # method as the five above. This is the sixth cut and the first whose write
  # list is wide because of a seam rather than because of a purge:
  #
  #   - `app/composition/domains.py` declares `_BUILD_LISTS_REPOSITORIES` as
  #     twenty repositories, and `app/db/dynamo/registry.py`'s `tables_for`
  #     maps each to a table suffix of the same name, so twenty repositories are
  #     twenty tables. `backend/tests/entrypoints/test_repository_bundles.py`
  #     recomputes that tuple from the real import graph, so the bundle is a
  #     checked statement of what this function can reach.
  #   - Twenty in the bundle, seventeen granted, and the three-table gap is
  #     `car_makes`, `car_models` and `reports`. `car_makes` and `car_models`
  #     are reached only from `PartService._make_names`, which serves the
  #     filter-options route in `catalog` and nothing here; `_validate_car_ids`,
  #     which is the car read this domain does make, calls
  #     `repos.car_generations.get_many` and touches neither. `reports` is
  #     reached only from `purge_related_rows_for_parts`, which is the part
  #     purge and is a `catalog` and `admin` path. Granting a table on the
  #     strength of an import rather than a call is what the five entries above
  #     refused.
  #   - One table is granted that the bundle does not name, and finding it is
  #     the substantive result of this row's derivation. `app_settings` is read
  #     on `POST /api/build-lists` and `POST /api/build-lists/{id}/copy`:
  #     `build_list_service._enforce_free_tier_limit` calls `is_user_premium`
  #     with `check_kill_switch=True`, which calls `is_premium_system_disabled`
  #     in `app/api/utils/subscription_utils.py`, which does
  #     `AppSettingsRepository().premium_disabled()` and so a `GetItem` on the
  #     table. It constructs the repository directly rather than going through
  #     `get_repositories()`, so the bundle guard never sees it and
  #     `test_repository_bundles.py` cannot catch it. Without this grant both
  #     create paths would fail with AccessDeniedException the moment the route
  #     moved, and a speculative plan would be green. It is in `read_tables`:
  #     the kill switch is only ever read here, and `admin` owns the write.
  #   - Eleven tables are written, and every one has a named caller.
  #     The four this domain owns per section 1.2 are the obvious four:
  #     `build_lists` from create, the base router's PUT and DELETE, copy and
  #     the three image routes; `build_list_parts`, `build_list_phases` and
  #     `build_list_labor_estimates` from their own create, update and delete
  #     routes and from the delete cascade.
  #     `build_logs` and `build_log_posts` are section 1.2's "created with the
  #     list": `build_list_service._create_build_log` calls
  #     `repos.build_logs.create` from both `create` and `copy_build_list`, and
  #     `delete` passes `build_log_delete_actions`, which deletes the log's
  #     posts and then the log.
  #     The remaining five are one route, `POST
  #     /api/build-list-parts/{build_list_id}/create-and-add-part`, and they are
  #     section 1.2's price capture arriving here rather than only in `catalog`.
  #     Both of its branches reach
  #     `part_listing_service.create_or_update_listing_and_price`, the existing
  #     part branch directly and the new part branch through
  #     `part_service.create_part`. That chokepoint writes `part_listings` and
  #     `part_price_history` and updates `parts.best_price_cents` in one
  #     `transact_write`, and `create_part` additionally calls
  #     `repos.parts.create_unique` with `repos.part_cars.sync_actions`. It then
  #     calls `evaluate_alerts_for_listing`, which writes
  #     `part_price_alerts.last_fired_at` after a send. Section 1.2's "also
  #     written today by" column names `build-lists` against `part_listings` and
  #     `part_price_history` for exactly this reason, and the column is right.
  #     Seam 2 and row 28 are what eventually narrow this. Until then the grant
  #     follows the writer, and on this route the writer is this function.
  #   - Six tables are read only. `users` is read on the twenty-eight routes
  #     that touch an auth dependency, because `get_current_user` and
  #     `get_optional_current_user` both resolve the token subject through
  #     `repos.users.get_by_username`, and again in the alert evaluator, which
  #     calls `repos.users.get(alert.user_id)` for the address. `car_generations`
  #     is `_verify_car_exists` on create and update, `GET
  #     /api/build-lists/car/{car_id}` and `PartService._validate_car_ids`.
  #     `categories`, `part_manufacturers` and `retailers` are the three
  #     existence checks `create_part` and the create-and-add-part route make
  #     before writing, plus the retailer the alert evaluator resolves for the
  #     email body; none of the three is created here, because
  #     `get_or_create_retailer` and `get_or_create_part_manufacturer_by_name`
  #     are called only from `catalog`'s own two modules. `votes` is
  #     `repos.votes.tallies` and `user_votes` on `GET
  #     /api/build-lists/with-votes` and is never written from this domain, which
  #     row 24 is what made true. `app_settings` is the kill switch above.
  #   - Row 23's tombstone reads need no grant of their own and are worth naming
  #     anyway, because they are why two of the reads above are load bearing
  #     rather than incidental: `drop_tombstoned_values` filters `parts` on the
  #     build-list part listings and on `with-votes`, and `get_current_user`
  #     checks the user's own flags. `parts` is in `tables` rather than
  #     `read_tables` because a table appears in exactly one of the two lists
  #     and the write set is the wider grant.
  #   - `rate-limits` is in `tables` for the reason all five entries above
  #     record: the shared limiter's counter table, reached from the middleware
  #     rather than from a repository, and it fails open, so withholding it
  #     turns layer 2 off silently rather than failing.
  #   - `secrets` is true. Twenty of the thirty-four routes require a token and
  #     eight more accept an optional one, so `SECRET_KEY` is read on most
  #     requests; the descriptor sets `requires_secrets=("SECRET_KEY",)`.
  #   - `s3` is true, and this is the correction to section 3.4 the schema
  #     comment above records. `DELETE
  #     /api/build-lists/{build_list_id}/images/{image_index}` calls
  #     `storage_service.delete_image(removed_key)`, which is a real
  #     `delete_object` against the user images bucket. It is the only S3 call
  #     in any of the four modules: `append-images` and `primary-image` reorder
  #     file keys in DynamoDB and upload nothing, and the keys themselves come
  #     from the build list row rather than from a listing. So
  #     `s3_delete_only` is set and the grant is `s3:DeleteObject` plus
  #     `s3:ListBucket`, without `s3:PutObject` or `s3:GetObject`. `ListBucket`
  #     is not optional despite nothing here listing: it is what authorizes the
  #     `head_bucket` that `StorageService._ensure_client` makes once per cold
  #     start, and without it the service disables itself and the delete becomes
  #     a silent no-op that leaves the object orphaned in the bucket while the
  #     row loses its key.
  #   - SES is not granted and no `EMAIL_FROM` is set, for the same reason row
  #     21 gave and with one more step to it. The price alert email is genuinely
  #     reachable from this domain, unlike from `admin`, because
  #     `evaluate_alerts_for_listing` runs at the end of the price capture the
  #     create-and-add-part route triggers. It still sends nothing:
  #     `app/core/email.py`'s `_send` returns early unless `EMAIL_ENABLED`, that
  #     setting defaults to false, and `local.lambda_domain_environment` sets it
  #     on no domain function. The evaluator treats the False as a failed send,
  #     leaves `last_fired_at` alone and retries on the next observation, so the
  #     behaviour after this cut is the behaviour before it. Row 25 is seam 4,
  #     which moves the email onto a stream handler with the grant and the
  #     environment key together, and that is where it should land rather than
  #     here.
  #
  # 1024 MB, and the first entry above `media`'s 512. Section 3.3 sets the
  # starting sizes and names `catalog` and `build-lists` as the two that start
  # at the monolith's 1024; the four cuts before this one came in under 3.3's
  # figure for the rest rather than over it, so this is the paragraph being
  # followed and not stretched. It is the right call on this domain's own terms:
  # `GET /api/build-lists/with-votes` reads build lists, joins them to their
  # parts, resolves those parts and then tallies votes over the set, holding
  # every intermediate in memory, and the create-and-add-part route runs a
  # dedup across three lookup paths before a multi-table `transact_write`. Both
  # are wider than anything the four 256 MB domains serve. Memory is also CPU on
  # Lambda, so the number is as much about the latency of those joins as about
  # the footprint, and it is the cheapest knob to lower if the duration and the
  # max-memory-used say the joins are smaller than section 3.3 assumed.
  # How `identity`'s table lists were derived, by row 27 and by the same method
  # as the six above. This is the narrowest write list of any domain that writes
  # anything, and the first entry whose grants are not a subset of DynamoDB:
  #
  #   - `app/composition/domains.py` declares `_IDENTITY_REPOSITORIES` as
  #     `users`, `oauth_accounts` and `webauthn_credentials`, and
  #     `app/db/dynamo/registry.py`'s `tables_for` maps each of those three to a
  #     table suffix of the same name, so the three repositories are three
  #     tables. `backend/tests/entrypoints/test_repository_bundles.py` recomputes
  #     that tuple from the real import graph, so the bundle is a checked
  #     statement of what this function can reach.
  #   - All three are written, and `read_tables` is empty for the first time on
  #     any cut. That is the shape of an authentication domain rather than an
  #     oversight: every table it can reach, it mutates. `core.py` and
  #     `two_factor.py` call `repos.users.update` for the password reset, the
  #     email verification flag and the 2FA secret; `oauth.py` calls
  #     `repos.oauth_accounts.create_link`, `.delete_link` and `.create_actions`
  #     and, on the Google signup path, `repos.users.create_actions`; and
  #     `webauthn.py` calls `.create_credential`, `.update` and
  #     `.delete_credential` on `repos.webauthn_credentials`. The reads on those
  #     same three tables (`get_by_email`, `get_by_username`, `get`,
  #     `list_by_user`, `get_by_provider_account`) need no separate entry,
  #     because a table appears in exactly one of the two lists and the write
  #     set is the wider grant.
  #   - `users` is written here and `users` is the domain that owns it, per
  #     section 1.2's "also written today by" column, which names `identity` for
  #     the oauth link, the webauthn registration and the password and 2FA
  #     changes. That cross-domain write is seam 1's neighbour and it stays
  #     synchronous: it is not one of the five seams section 1.3 unwinds, because
  #     it is a field update on a row the caller already owns rather than a
  #     cascade. Row 31 is where `users` moves, and the two functions write
  #     disjoint attributes of the same row until then.
  #   - The uniqueness reservations need no table of their own. Both
  #     `create_actions` paths open with `ensure_unique_action`, which
  #     `app/db/dynamo/repository.py` builds as a `Put` against `self.table_name`,
  #     so a username, email, provider-account or user-provider reservation is a
  #     row in the same table as the entity and is covered by that table's grant.
  #     `TransactWriteItems` is in the twelve write actions, which is what makes
  #     the two-table Google signup transaction work across `users` and
  #     `oauth_accounts` in one call.
  #   - No table is read that is not also written, and no table outside the
  #     bundle is reached at all. Row 26 found `app_settings` read through a
  #     directly constructed `AppSettingsRepository()` in
  #     `app/api/utils/subscription_utils.py`, which the bundle guard cannot see,
  #     and warned that the same shape could hide elsewhere. It does not hide
  #     here: that file holds the only direct repository construction in `app/`,
  #     and its two callers are both in `build_list_service`, which no identity
  #     route reaches. The four auth modules import
  #     `app.api.services.user_service` for `user_read` alone, and that helper
  #     touches `oauth_accounts`, which is already granted.
  #   - `rate-limits` is in `tables` for the reason every entry above records: it
  #     is the shared limiter's counter table, reached from the middleware stack
  #     that `app/composition/wiring.py` installs on every domain application
  #     rather than from a repository, so the bundle cannot name it, and the
  #     limiter fails open, so withholding it would turn layer 2 off silently
  #     rather than failing.
  #   - `secrets` is true, and this is the domain that makes the key matter. It
  #     is the only one that mints a token rather than merely verifying one:
  #     `create_access_token` signs the login token, the refresh token, the
  #     one-hour email verification token and the one-hour password reset token,
  #     and its descriptor sets `requires_secrets=("SECRET_KEY",)`.
  #   - `s3` is false, and it takes a paragraph rather than a line because there
  #     is a reachable S3 call and the decision is to leave it ungranted. No auth
  #     module imports `storage_service`, constructs an S3 client or names the
  #     bucket, and the avatar upload section 3.4 pairs with `users` is a `users`
  #     route. What is reachable is avatar *presigning* on the way out: every
  #     route returning a user goes through `user_service.user_read`, and
  #     `UserRead`'s `image_urls` field serializer calls
  #     `apply_image_url_presigning`, which reaches
  #     `storage_service.get_presigned_url` and so the `head_bucket` in
  #     `_ensure_client`.
  #
  #     It is left ungranted because the fallback is graceful and because the
  #     precedent is already set. `get_presigned_url_from_file_key` wraps the
  #     call in a `try` and returns the raw file key on any failure with a
  #     warning, which the comment there records the frontend as handling, so the
  #     response is a 200 either way and nothing 500s. And `vehicles`, cut in row
  #     20 with `s3 = false`, already serves `PublicUserRead` through the same
  #     serializer on its search route, so this cut changes nothing that row 20
  #     did not already settle. Granting `s3:GetObject` and `s3:ListBucket` to
  #     restore presigned avatars on the login response is a widening that should
  #     be argued on its own if the raw keys turn out to matter, and it would
  #     have to cover row 20's domain too rather than this one alone.
  #   - One bundle-guard bypass is reachable in process and is deliberately not
  #     granted, which is the row 26 shape appearing in a form that does not
  #     need a grant. `app/api/services/sitemap_service.py` calls
  #     `get_repositories()` directly rather than taking the injected bundle, so
  #     it reaches `parts`, `build_lists` and `car_generations`, and
  #     `add_root_routes` puts `/sitemap.xml` and `/sitemap-{name}.xml` on every
  #     domain application including this one. No gateway request can reach it:
  #     the only route keys pointing here are `/api/auth` and its `{proxy+}`, and
  #     the sitemap paths have no key of their own, so they resolved through
  #     `$default` to the monolith while it existed and answer 404 at the gateway
  #     since row 32 removed it. Either way no gateway request reaches the code,
  #     and the three tables are left out rather than granted for a path that
  #     cannot be called.
  #     It would become a real gap the moment a sitemap route key were added, and
  #     it is recorded here so that change is made with the grant rather than
  #     after an AccessDeniedException.
  #   - No new environment key is needed for Google sign-in, which is worth
  #     recording because the domain map suggests otherwise. `oauth.py` verifies
  #     an ID token and never exchanges an authorization code, so it reads
  #     `GOOGLE_CLIENT_ID` as the audience and no client secret exists anywhere
  #     in the settings. That id carries a default in `app/core/config.py` and is
  #     set by no Terraform on the monolith either, so the cut function verifies
  #     Google tokens exactly as the monolith does today with nothing added here.
  #
  # SES is granted, and `identity` is the first HTTP function to carry it. Every
  # cut before this one refused the grant because the reachable send could not
  # fire or was not reachable at all, and row 25 put `admin`'s half on the stream
  # consumer that actually sends. This row is section 3.4's other half and the
  # argument runs the other way, because the failure mode is not silence:
  #
  #   - Two routes send. `POST /api/auth/verify-email` calls `send_verify_email`
  #     and `POST /api/auth/reset-password` calls `send_reset_password_email`,
  #     both from `app/api/endpoints/auth/core.py` and both synchronously on the
  #     request thread.
  #   - Both raise on a failed send. Each is written as
  #     `if not send_...(...): ResponsePatterns.raise_internal_server_error(...)`,
  #     so a send that returns False is a 500 to the caller rather than a warning
  #     in a log. That is the difference from row 26, where the price alert
  #     evaluator treated a False as a retryable non-event and the behaviour
  #     after the cut equalled the behaviour before it.
  #   - So the environment keys come with the grant. `app/core/email.py`'s
  #     `_send` returns False immediately unless `EMAIL_ENABLED`, and the
  #     monolith's `local.lambda_environment` in lambda.tf sets `EMAIL_ENABLED`
  #     to "true" and `EMAIL_FROM` to `local.email_from` today, so these two
  #     routes really do send in both environments. Cutting the prefix onto a
  #     function without all three of the grant, the switch and the sender would
  #     turn email verification and password reset into unconditional 500s, on a
  #     plan that was green. This is the one place where withholding the grant
  #     would change behaviour rather than preserve it.
  #   - `API_URL` is still not set, matching the monolith and the other domain
  #     functions. The verification link is built from `settings.api_base_url`,
  #     which falls back to the API host derived from `APP_ENVIRONMENT` when the
  #     variable is unset, and `APP_ENVIRONMENT` is set on every domain function,
  #     so staging mails staging links.
  #
  # 512 MB rather than the 256 the four small domains take. Section 3.3 names
  # only `catalog` and `build-lists` for 1024 and leaves the rest at its 512
  # starting size, so this is the paragraph being followed rather than stretched;
  # the four cuts that came in at 256 did so because their routes are JSON over
  # DynamoDB with no native work anywhere in them, and that is not true here.
  # Three of this domain's paths are CPU bound native work, and memory is CPU on
  # Lambda: `bcrypt` hashing on the login and the password reset routes, the
  # `webauthn` attestation and assertion verification on the four passkey
  # routes, and `POST /api/auth/2fa/setup`, which builds a QR code with `qrcode`
  # and encodes it through PIL's `img.save(buffer, "PNG")`. That last one is
  # Pillow on the request thread, which is the same reason `media` takes 512.
  # 256 would probably serve, since none of the three is `media`'s image
  # pipeline, but this is the login path for the whole application and latency
  # here is felt on every session rather than on an occasional upload. Memory is
  # the cheapest knob to lower if the duration and the max-memory-used say so.
  #
  # How `catalog`'s two table lists were derived, by row 29 and by the same
  # method as the seven above. This is the largest domain by route count, 43
  # across four prefixes, and it is the first entry whose bundle was narrowed by
  # a seam landing in the row immediately before it:
  #
  #   - `app/composition/domains.py` declares `_CATALOG_REPOSITORIES` as twelve
  #     repositories: `users`, `car_makes`, `car_models`, `car_generations`,
  #     `categories`, `part_manufacturers`, `retailers`, `parts`, `part_cars`,
  #     `part_listings`, `part_price_history` and `votes`.
  #     `app/db/dynamo/registry.py`'s `tables_for` maps each of the twelve to a
  #     table suffix of the same name, so twelve repositories are twelve tables,
  #     and `backend/tests/entrypoints/test_repository_bundles.py` recomputes
  #     that tuple from the real import graph, so the bundle is a checked
  #     statement of what this function can reach.
  #   - The tuple was fifteen until row 28 and is twelve now, and that is seam 2
  #     landing rather than a narrowing this row performed. `build_list_parts`,
  #     `part_price_alerts` and `reports` were declared because every delete
  #     route called `purge_related_rows_for_parts`, which reached all four
  #     tables synchronously. Row 28 moved that cascade onto
  #     `carmodpicker-<env>-catalog-part-purge-consumer`, which names those
  #     repositories itself in `app/entrypoints/catalog_part_purge_consumer.py`
  #     and carries its own IAM in lambda_stream_consumers.tf. So the three
  #     tables are still written by `catalog`'s image, and they are written by
  #     the consumer function rather than by this one, which is exactly the
  #     grant following the writer. Cutting this domain a row earlier would have
  #     meant granting all three here for a cascade that no longer runs on the
  #     request thread.
  #   - Twelve in the bundle and eleven granted, so the bundle-to-grant gap is
  #     one table and it is `car_generations`. It is not ungranted for row 19's
  #     and row 20's reason, which is a repository reached only through an
  #     import: `part_service._car_generations` really does call
  #     `repos.car_generations.get_many` to hydrate fitment on a part read. It
  #     is granted, in `read_tables`. The genuinely ungranted pair is
  #     `car_makes` and `car_models`, which `part_service._make_names` reaches
  #     from the same fitment path, and they are granted too for the same
  #     reason. So this cut has no bundle-to-grant gap at all, the first of the
  #     eight, and that is what row 28's narrowing bought: with the purge gone,
  #     every repository the tuple names has a route that calls it.
  #   - Seven tables are written, plus the limiter's counter. `parts`,
  #     `part_manufacturers`, `retailers`, `part_cars`, `part_listings`,
  #     `part_price_history` and `categories` are seven of the eleven this
  #     domain owns per section 1.2, and each has a named caller.
  #     `part_service` calls `.create_unique`, `.save_unique`, `.update`,
  #     `.put` and `.delete_unique` on `repos.parts` and `.sync_actions` and
  #     `.unlink_action` on `repos.part_cars` from the create, update and delete
  #     routes; `part_manufacturers.py` calls `.update_unique` and
  #     `.delete_unique`; `retailers.py` calls `.create_unique`,
  #     `.update_unique` and `.delete_unique`, and `part_listing_service` calls
  #     `.create_unique` and `.update_unique` on the same repository from the
  #     get-or-create path; and `part_listing_service` writes `part_listings`
  #     through `.create_action`, `.put_action`, `.delete` and
  #     `.delete_for_part` and `part_price_history` through `.put_action` and
  #     `.delete_for_listing`, both from the price capture that
  #     `POST /api/parts/{part_id}/listings` and `POST /api/parts/price-history`
  #     drive.
  #   - `categories` is the seventh written table and it is the one worth
  #     stating, because `categories.py` is five `GET` routes and writes
  #     nothing. The write is not in the endpoint module: `part_service`'s
  #     create and update paths call `repos.categories.get` and `.get_many` to
  #     resolve the category on a part, which is a read, and the module's own
  #     routes are reads. It is in `tables` rather than `read_tables` anyway
  #     because `catalog` owns it per section 1.2 and
  #     `POST /admin/db-ops/init/part-categories` seeds it from the `admin`
  #     image, so a future catalog-side category write lands with the grant
  #     rather than after an `AccessDeniedException`. That is the one place this
  #     entry grants on ownership rather than on a call, and it is called out
  #     here rather than left to be discovered.
  #   - Four tables are read only. `users` is read before the seventeen routes
  #     that verify a token run, because `get_current_user` and
  #     `get_current_admin_user` both call `repos.users.get_by_username` to
  #     resolve the token subject, and `part_service.list_with_votes` passes the
  #     resolved user through. `votes` is read by `part_service.with_votes`,
  #     which calls `repos.votes.tallies` and `repos.votes.user_votes` to
  #     decorate `GET /api/parts/with-votes`; the write that used to sit
  #     alongside it went to `catalog-votes-consumer` in row 24, which is why
  #     `votes` is a read here and not a write. `car_makes`, `car_models` and
  #     `car_generations` are `vehicles`' three, read by
  #     `part_service._make_names` and `._car_generations` to render fitment on
  #     a part, which is a cross-domain read and is allowed with read-only IAM.
  #   - `rate-limits` is in `tables` for the reason every entry above records:
  #     it is the shared limiter's counter table, reached from the middleware
  #     stack rather than from a repository, so the bundle cannot name it, and
  #     the limiter fails open, so withholding it would silently turn layer 2
  #     off for this domain rather than failing.
  #   - `secrets` is true. Seventeen of the 43 routes verify a token and the
  #     descriptor sets `requires_secrets = ("SECRET_KEY",)`, so the runtime
  #     policy carries `secretsmanager:GetSecretValue` and the environment
  #     carries `APP_SECRETS_ARN`.
  #   - `s3` is true and `s3_delete_only` is true, which is row 26's correction
  #     applying to a second domain. Section 3.4 named only `media` and `users`,
  #     reasoning from the domains whose names are about images;
  #     `DELETE /api/parts/{part_id}/images/{image_index}` calls
  #     `storage_service.delete_image`, a real `delete_object`, and it is the
  #     only S3 call in any of the four endpoint modules. `append-images` and
  #     `primary-image` only reorder file keys in DynamoDB. So the narrow flag
  #     rather than the broad one: `s3:DeleteObject` and `s3:ListBucket`,
  #     without `s3:PutObject` or `s3:GetObject`. `ListBucket` is not optional
  #     despite nothing here listing, for the reason row 26 recorded: it
  #     authorizes the `head_bucket` that `StorageService._ensure_client` makes
  #     once per cold start, and without it the service disables itself and the
  #     delete becomes a silent no-op that orphans the object while the row
  #     loses its key.
  #   - `ses` is false, and unlike `identity` the reason is that the send is not
  #     reachable from this function at all any more. The price alert email is
  #     `evaluate_alerts_for_listing`, which row 25 moved onto
  #     `admin-price-alerts-consumer` along with its grant and its `EMAIL_FROM`.
  #     `part_listing_service` no longer calls it inline, so a grant here would
  #     be configuration for a code path that cannot execute, which is the
  #     argument rows 21 and 26 both made. Section 3.4 said `catalog` loses SES
  #     when seam 4 moves, and this is that.
  #
  # 1024 MB, per section 3.3, which names `catalog` and `build-lists` as the two
  # that start at the monolith's size rather than at 512. Right on the domain's
  # own terms too, and for a different reason than `build-lists`':
  # `GET /api/parts/with-votes` pages parts, tallies votes over the whole page
  # and hydrates fitment through `_make_names` and `_car_generations`, holding
  # every intermediate in memory, and the price capture behind
  # `POST /api/parts/{part_id}/listings` dedups a listing across three lookup
  # paths before a multi-table `transact_write`. This is also the busiest
  # domain in the application by route count, so it is the last one to tune down
  # on a guess. Memory is the cheapest knob to lower once a week of duration and
  # max-memory-used data says so.
  #
  # How `users`' two table lists were derived, by row 31 and by the same method
  # as the eight above. This is the ninth and last cut, and it is the entry
  # whose bundle was narrowed hardest by the row immediately before it:
  #
  #   - `app/composition/domains.py` declares `_USERS_REPOSITORIES` as three
  #     repositories: `users`, `app_settings` and `oauth_accounts`.
  #     `app/db/dynamo/registry.py`'s `tables_for` maps each of the three to a
  #     table suffix of the same name, so three repositories are three tables,
  #     and `backend/tests/entrypoints/test_repository_bundles.py` recomputes
  #     that tuple from the real import graph, so the bundle is a checked
  #     statement of what this function can reach.
  #   - The tuple was twenty-three of the twenty-five until row 30, and that is
  #     seam 1 landing rather than a narrowing this row performed.
  #     `_delete_user_everywhere` deleted a user and then wrote into roughly
  #     fifteen tables across `identity`, `catalog`, `build-lists`,
  #     `build-logs`, `moderation` and `admin`, on the request thread inside a
  #     29 second Lambda. Row 30 moved that cascade onto
  #     `carmodpicker-<env>-users-delete-consumer`, which names those
  #     repositories itself in `app/entrypoints/users_delete_consumer.py` and
  #     carries its own IAM in lambda_stream_consumers.tf, and twenty entries
  #     went with it. So those tables are still written by the `users` image,
  #     and they are written by the consumer function rather than by this one,
  #     which is the grant following the writer exactly as row 28 did it for
  #     `catalog`. Cutting this domain a row earlier would have meant granting
  #     roughly fifteen tables here for a cascade that no longer runs on the
  #     request thread, and this entry would have been the widest of the nine
  #     rather than the second narrowest.
  #   - Three in the bundle and three granted, so there is no bundle-to-grant
  #     gap. `catalog` was the first cut to manage that and this is the second,
  #     and for the same reason: the seam landed in the row before.
  #   - Two tables are written, plus the limiter's counter. `users` is this
  #     domain's own and every mutating route reaches it:
  #     `users.py` calls `repos.users.create_user` on the signup route,
  #     `.update_user` on the self and admin update routes, `.update` on both
  #     profile-picture routes and on the tombstone in `_delete_user`, and
  #     `.delete_user` for the hard delete and its two unique reservations.
  #     `app_settings` is written by `PUT /api/app-settings`, which calls
  #     `repos.app_settings.update_settings`, and read by the public `GET` on
  #     the same path through `.get_or_create`, which is itself a write on a
  #     cold singleton, so the table is in `tables` rather than in
  #     `read_tables` on the strength of the read path as well as the write.
  #   - `oauth_accounts` is the one read-only table, and it is the one worth
  #     stating because it was invisible until row 30. It is a genuine
  #     cross-domain read rather than a leftover: `user_service.user_read` calls
  #     `repos.oauth_accounts.list_by_user` and `user_reads` calls
  #     `.list_by_users`, and every route in this domain that returns a user
  #     goes through one of the two, so the read is on eleven of the fourteen
  #     routes rather than on an edge case. `identity` writes the table and this
  #     domain only reads it, which is why it is `read_tables` here and `tables`
  #     there.
  #
  #     The reason it was invisible is worth keeping rather than leaving in the
  #     row 30 pull request. The import-graph analyzer in
  #     `test_repository_bundles.py` matches attribute accesses whose receiver
  #     is named `repos`, and `user_service.py` had named its local
  #     `repositories`, so this read did not appear in the graph at all. It was
  #     masked for as long as the old twenty-three entry tuple happened to
  #     declare `oauth_accounts` for cascade reasons. Row 30's trim computed
  #     `users` as two entries, which would have been a `RepositoryNotInBundle`
  #     on `GET /users/me` on every request the moment this row applied, and it
  #     was fixed by renaming the local rather than by widening the matcher. The
  #     name is load bearing, the comment on `user_read` says so, and this cut
  #     is the row that would have paid for it.
  #   - `rate-limits` is in `tables` for the reason every entry above records:
  #     it is the shared limiter's counter table, reached from the middleware
  #     stack rather than from a repository, so the bundle cannot name it, and
  #     the limiter fails open, so withholding it would silently turn layer 2
  #     off for this domain rather than failing.
  #   - `secrets` is true. Every one of the fourteen routes but the public
  #     `GET /api/app-settings/` is behind `get_current_user` or
  #     `get_current_admin_user`, both of which decode a token, and the
  #     descriptor sets `requires_secrets = ("SECRET_KEY",)`.
  #   - `s3` is true and `s3_delete_only` is **false**, and this is the second
  #     and last entry to take the broad flag after `media`. Section 3.4 named
  #     `media` and `users` as the two, and unlike row 26's and row 29's
  #     corrections this one lands exactly where 3.4 put it.
  #     `POST /api/users/me/profile-picture` calls `storage_service.upload_image`,
  #     a real `put_object`, and then `delete_image` on the key it replaces;
  #     `DELETE /api/users/me/profile-picture` calls `delete_image` on its own.
  #     So `s3:PutObject` and `s3:DeleteObject` are both reached from the same
  #     route, which is what rules out row 26's narrow flag here.
  #     `s3:GetObject` rides along with the broad flag and is also genuinely
  #     reached, on the way out rather than on the way in: `user_read`'s
  #     `image_urls` serializer calls `apply_image_url_presigning`, which is the
  #     path row 27 left ungranted on `identity` because the fallback there is
  #     graceful. Here the grant arrives anyway with the upload, so this is the
  #     one domain where avatars presign rather than falling back to raw keys,
  #     and row 27's note that a widening "would have to cover row 20's domain
  #     too" is untouched: `vehicles` still serves `PublicUserRead` with
  #     `s3 = false` and still falls back.
  #   - `ses` is false. No route in either endpoint module imports
  #     `app/core/email.py` or reaches a send. Account deletion sends nothing,
  #     and the verification and reset mail is `identity`'s, granted there in
  #     row 27.
  #   - No SQS grant, and that is not an omission. Row 30's cascade is driven
  #     off the `users` DynamoDB stream and the `user-delete` work queue, and
  #     the enqueue is the consumer's own, not this function's: `_delete_user`
  #     writes a tombstone and hard deletes, and nothing in `app/api/endpoints/`
  #     constructs an SQS client or names a queue. The stream is read by the
  #     event source mapping under the consumer's role.
  #
  # 512 MB, per section 3.3, which starts every domain but `catalog` and
  # `build-lists` there. Right on this domain's own terms: the widest thing it
  # does is `GET /api/users/` paginating in memory over a search or a full list
  # and hydrating each row's linked accounts through `user_reads`' batched
  # `list_by_users`, which is one Dynamo read per page rather than a join, and
  # the profile-picture upload streams a single image through
  # `storage_service`. Neither holds the kind of intermediate the two 1024 MB
  # domains do.
  lambda_domains_declared = {
    media = {
      secrets        = true
      s3             = true
      s3_delete_only = false
      ses            = false
      memory         = 512
      tables         = ["image_source_mappings", "rate-limits"]
      read_tables    = ["users", "car_generations", "parts", "build_lists"]
    }
    build-logs = {
      secrets        = true
      s3             = false
      s3_delete_only = false
      ses            = false
      memory         = 256
      tables         = ["build_log_posts", "rate-limits"]
      read_tables    = ["users", "build_lists", "build_logs"]
    }
    moderation = {
      secrets        = true
      s3             = false
      s3_delete_only = false
      ses            = false
      memory         = 256
      # Three written tables, down from four. Row 24 moved `parts` to
      # `read_tables`; see the derivation above for why it was ever written and
      # what replaced the write.
      tables      = ["votes", "reports", "bug_reports", "rate-limits"]
      read_tables = ["users", "build_lists", "car_generations", "parts"]
    }
    vehicles = {
      secrets        = false
      s3             = false
      s3_delete_only = false
      ses            = false
      memory         = 256
      # The limiter's counter table and nothing else. Every route this domain
      # serves is a public read; see the derivation above.
      tables = ["rate-limits"]
      read_tables = [
        "car_generations",
        "car_models",
        "car_makes",
        "build_lists",
        "users",
        "parts",
        "part_manufacturers",
      ]
    }
    admin = {
      secrets        = true
      s3             = false
      s3_delete_only = false
      ses            = false
      memory         = 256
      # Fourteen written tables, thirteen of them real and the fourteenth the
      # limiter's counter. This is the widest write list of the nine by a wide
      # margin, and it is the domain's whole purpose rather than a failure to
      # narrow it: the two admin modules seed and purge six domains' tables by
      # design. The derivation above names the call behind every one.
      #
      # Row 28 removed `build_list_parts`, which is seam 2 landing exactly where
      # the derivation above said it would. It was granted because
      # `POST /admin/db-ops/parts/delete-all` ran the part purge, and the purge
      # called `.batch_delete` on it. Nothing in `admin/stats` or
      # `admin/db_ops` reaches that repository now, so the grant went with the
      # cascade to `carmodpicker-<env>-catalog-part-purge-consumer`.
      #
      # `votes` stays: `POST /admin/db-ops/car-generations/delete-all` calls
      # `.delete_for_entity_type("car_generation")` on it, so the purge was
      # never its only writer. `reports` stays because `admin/stats` calls
      # `.count_by_entity_type()` on it, and a table appears in exactly one of
      # the two lists with the write set being the wider grant.
      # `part_price_alerts` stays because `admin` owns it.
      tables = [
        "part_price_alerts",
        "car_makes",
        "car_models",
        "car_generations",
        "categories",
        "part_manufacturers",
        "parts",
        "part_cars",
        "part_listings",
        "part_price_history",
        "build_lists",
        "votes",
        "reports",
        "rate-limits",
      ]
      read_tables = [
        "users",
        "oauth_accounts",
        "webauthn_credentials",
        "build_list_phases",
        "build_logs",
        "image_source_mappings",
      ]
    }
    build-lists = {
      secrets = true
      # The gallery delete and nothing else; see the derivation above. The
      # narrow flag rather than the broad one, so this function can delete an
      # image it owns and cannot upload or read one.
      s3             = true
      s3_delete_only = true
      ses            = false
      memory         = 1024
      # Twelve written tables, eleven of them real and the twelfth the limiter's
      # counter. The four owned build-list tables, the two build-log tables the
      # create and delete paths touch, and the five the create-and-add-part
      # route's price capture writes.
      tables = [
        "build_lists",
        "build_list_parts",
        "build_list_phases",
        "build_list_labor_estimates",
        "build_logs",
        "build_log_posts",
        "parts",
        "part_cars",
        "part_listings",
        "part_price_history",
        "part_price_alerts",
        "rate-limits",
      ]
      read_tables = [
        "users",
        "app_settings",
        "car_generations",
        "categories",
        "part_manufacturers",
        "retailers",
        "votes",
      ]
    }
    identity = {
      secrets        = true
      s3             = false
      s3_delete_only = false
      # The first HTTP function to hold the grant, and the first cut where
      # withholding it would change behaviour rather than preserve it. The
      # verify-email and reset-password routes raise a 500 on a failed send; see
      # the derivation above.
      ses    = true
      memory = 512
      # Three written tables and the limiter's counter, and no read-only table at
      # all: every table this domain can reach, it mutates.
      tables      = ["users", "oauth_accounts", "webauthn_credentials", "rate-limits"]
      read_tables = []
    }
    catalog = {
      secrets = true
      # The gallery image delete and nothing else, the same shape row 26 found
      # for `build-lists`. The narrow flag rather than the broad one, so this
      # function can delete an image it owns and cannot upload or read one; see
      # the derivation above.
      s3             = true
      s3_delete_only = true
      # False, and unlike `identity` because the send is unreachable rather than
      # merely inert: row 25 moved the price alert email onto
      # `admin-price-alerts-consumer` with its grant, which is section 3.4's
      # "catalog loses SES when seam 4 moves".
      ses    = false
      memory = 1024
      # Eight written tables, seven of them real and the eighth the limiter's
      # counter. Seven of the eleven tables this domain owns; the other four
      # moved to `catalog-part-purge-consumer` with the cascade in row 28.
      tables = [
        "parts",
        "part_manufacturers",
        "retailers",
        "categories",
        "part_cars",
        "part_listings",
        "part_price_history",
        "rate-limits",
      ]
      read_tables = [
        "users",
        "votes",
        "car_makes",
        "car_models",
        "car_generations",
      ]
    }
    users = {
      secrets = true
      # The broad flag, and the second and last entry to take it after `media`.
      # `POST /api/users/me/profile-picture` uploads and then deletes the key it
      # replaces, so `s3:PutObject` and `s3:DeleteObject` are both reached from
      # one route, which is what rules out row 26's narrowing here. Section 3.4
      # named `media` and `users` as the two and this one lands where it said.
      s3             = true
      s3_delete_only = false
      # No route in either endpoint module reaches a send. The verification and
      # reset mail is `identity`'s, granted there in row 27, and account
      # deletion sends nothing.
      ses    = false
      memory = 512
      # Two written tables and the limiter's counter. `users` is this domain's
      # own and `app_settings` is the global singleton, written by the admin PUT
      # and created on first read by `get_or_create`.
      tables      = ["users", "app_settings", "rate-limits"]
      read_tables = ["oauth_accounts"]
    }
  }

  # The bootstrap gate, and the whole of what makes this root promotable to a
  # fresh account without a knowingly failing apply.
  #
  # A domain function is created from an image, and Lambda pulls and optimises
  # that image at CreateFunction, so the tag has to already exist in the
  # repository. In a fresh account the repositories themselves do not exist
  # until this root's first apply, so there is no tag anything could have
  # pushed and no value of var.bootstrap_image_tag that would resolve. That is
  # a chicken and egg, not a misconfiguration: the repositories have to exist
  # before the images, and the images before the functions.
  #
  # Setting bootstrap_image_tag to "" is how an operator says "this account has
  # no images yet". The declared map above then resolves to empty, so the apply
  # creates the ECR repositories, the IAM roles including the CodeArtifact
  # grants, Transaction Search, the buckets, the tables and the API, and
  # creates no domain function and cuts no route. Deploy Backend can then push
  # the nine images, the operator sets the real tag, and the second apply
  # creates the functions and their routes together.
  #
  # Function creation and route cut stay in the same apply on purpose.
  # verify-route-cuts in .github/workflows/deploy-backend.yml hardcodes the
  # domain list, so a function that exists without its routes makes that job
  # probe the prefix and exit 1. Before row 32 that showed up as the access log
  # reading routeKey "$default", the monolith having answered; with `$default`
  # gone the same middle state is a 404 from the gateway instead. Gating both
  # sets on the same condition is what keeps that state from existing at all.
  #
  # Once the tag is set this local is the declared map, byte for byte, so an
  # environment that already has its functions sees no change from this gate.
  domain_functions_enabled = var.bootstrap_image_tag != ""

  lambda_domains = local.domain_functions_enabled ? local.lambda_domains_declared : {}

  # DynamoDB actions a domain gets on a table it writes. The same twelve the
  # monolith's runtime policy carries, so a domain moving off the monolith
  # cannot lose an action it was relying on.
  dynamodb_domain_write_actions = [
    "dynamodb:BatchGetItem",
    "dynamodb:BatchWriteItem",
    "dynamodb:ConditionCheckItem",
    "dynamodb:DeleteItem",
    "dynamodb:DescribeTable",
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:Query",
    "dynamodb:Scan",
    "dynamodb:TransactGetItems",
    "dynamodb:TransactWriteItems",
    "dynamodb:UpdateItem",
  ]

  # And on a table it only reads. Five, as section 3.4 says.
  # TransactGetItems and ConditionCheckItem are left out on purpose: nothing in
  # a read only path uses them, and including them would blur the line the least
  # privilege claim rests on.
  dynamodb_domain_read_actions = [
    "dynamodb:BatchGetItem",
    "dynamodb:DescribeTable",
    "dynamodb:GetItem",
    "dynamodb:Query",
    "dynamodb:Scan",
  ]

  # Table and index ARNs per domain, resolved through module.dynamodb. The
  # /index/* wildcard is on both sets because a Query naming an index is
  # authorized against the index ARN and not the table's: `media` reads `parts`
  # and `build_lists` through their owner indexes in the orphan sweep, and
  # `image_source_mappings` carries its own.
  lambda_domain_write_arns = {
    for name, domain in local.lambda_domains : name => flatten([
      for table in domain.tables : [
        module.dynamodb.table_arns[table],
        "${module.dynamodb.table_arns[table]}/index/*",
      ]
    ])
  }

  lambda_domain_read_arns = {
    for name, domain in local.lambda_domains : name => flatten([
      for table in domain.read_tables : [
        module.dynamodb.table_arns[table],
        "${module.dynamodb.table_arns[table]}/index/*",
      ]
    ])
  }

  # What every domain function is told about itself and its environment. The
  # monolith's `local.lambda_environment` in lambda.tf is the reference, minus
  # the four keys a domain function must not or need not carry:
  #
  #   - PORT and RUN_STARTUP_TASKS are baked into the image; see the file header.
  #   - EMAIL_FROM and EMAIL_ENABLED are `identity`'s and, from row 25,
  #     `admin`'s, per section 3.4's SES split, and row 27 is where the first
  #     half of that arrives. They are set on `identity` and on no other domain
  #     function: it is the one domain with a route that sends, and its two
  #     senders raise a 500 rather than logging when the send fails, so the pair
  #     lands with the grant rather than after it. `admin`'s half went to the
  #     stream consumer in lambda_stream_consumers.tf instead of to the HTTP
  #     function, because its one mail path is the price-drop alert, which is
  #     called from the price capture rather than from any route `admin` serves.
  #     Everywhere else a configured sender on a function with no ses:SendEmail
  #     grant would be a misleading configuration, so the key waits for the
  #     code.
  #   - SENTRY_SERVICE_NAME is gone. Row 16 removed `init_sentry` from every
  #     entrypoint, so nothing in a domain function reads it, and a Sentry
  #     variable on a function with no Sentry in it is a misleading
  #     configuration. The monolith in lambda.tf keeps its own until row 31.
  #
  # The two OTEL_ variables are the whole tracing contract, and they are what
  # row 16 turns on. `webbpulse.otel.configure_tracing` builds the pipeline
  # itself rather than running under `opentelemetry-instrument`, so
  # OTEL_EXPORTER_OTLP_TRACES_PROTOCOL, OTEL_PYTHON_DISTRO,
  # OTEL_PYTHON_CONFIGURATOR and OTEL_TRACES_SAMPLER are deliberately not set:
  # the protocol is implicit in the exporter class the package constructs, the
  # distribution is used as a library rather than a launcher, and the sampler is
  # passed explicitly so a ratio sampler in the environment cannot pre-drop the
  # spans the tail step exists to judge.
  #
  # WEBBPULSE_OTEL_SAMPLE_RATIO is the probability a *non-error* trace is kept.
  # Errors are kept whatever it says, which is the point of tail sampling and is
  # why 0.1 on production is not the 90 percent loss of failures a head sampler
  # at the same ratio would be. Staging keeps everything, because its traffic is
  # this repository's own tests and a smoke run.
  #
  # The endpoint is what un-gates the code. `configure_tracing` in
  # app/composition/wiring.py returns early unless it is set, which is what
  # keeps the test suite and a local run free of an exporter, so setting it here
  # is what makes tracing a Terraform change rather than a code change.
  lambda_domain_environment = {
    for name, domain in local.lambda_domains : name => merge(
      {
        DEBUG                 = "false"
        APP_ENVIRONMENT       = var.environment
        DYNAMODB_TABLE_PREFIX = local.prefix

        # Named explicitly rather than left to the prefix convention, for the
        # same reason lambda.tf names it: the function and the table cannot
        # drift to different names, and a plan error rather than a runtime
        # fail open is what surfaces if the table is ever renamed.
        RATE_LIMITS_TABLE = module.dynamodb.table_names["rate-limits"]

        FRONTEND_URL    = local.frontend_url
        ALLOWED_ORIGINS = local.allowed_origins

        WEBBPULSE_OTEL_SAMPLE_RATIO = var.environment == "production" ? "0.1" : "1.0"
        # Set explicitly rather than left to the package's own default, which
        # derives the same URL from AWS_REGION. Naming it here is what makes the
        # destination visible in the plan and in the console, so a function
        # exporting nowhere is a diff rather than an archaeology exercise.
        OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = "https://xray.${var.aws_region}.amazonaws.com/v1/traces"
      },
      domain.secrets ? { APP_SECRETS_ARN = module.app_secrets.arns["app"] } : {},
      # The sender and the switch, and only on a domain that sends.
      # `app/core/email.py` reads EMAIL_FROM for the SESv2 `FromEmailAddress`
      # and EMAIL_ENABLED as the switch that turns `_send` from a debug log into
      # a call, so both are needed and neither belongs on a function without
      # `ses:SendEmail`. Row 27 is what makes this branch non-empty for the
      # first time: `identity` is the only domain function that sends, and its
      # two senders raise a 500 rather than logging when `_send` returns False,
      # so the switch is as load bearing as the grant.
      #
      # API_URL is deliberately not set, matching the monolith and every other
      # function here. The verification link comes from `settings.api_base_url`,
      # which falls back to the API host derived from APP_ENVIRONMENT, and that
      # fallback is what keeps staging from mailing production links.
      domain.ses ? {
        EMAIL_FROM    = local.email_from
        EMAIL_ENABLED = "true"
      } : {},
      domain.s3 ? {
        USER_IMAGES_BUCKET = aws_s3_bucket.user_images.bucket
        # Empty means "the real S3 endpoint". The monolith filters empty values
        # out of its map for this key; here it is simply not set, which is the
        # same thing to pydantic and one fewer moving part.
      } : {},

      # The shared identity standard, on the `identity` function only and in
      # every environment. Row 4 of the identity adoption plan; terraform/identity.tf
      # has the rationale for the resources these names describe.
      #
      # NOTHING READS ANY OF THIS YET. The legacy HS256 flow in
      # `backend/app/api/endpoints/auth/` is what serves `/api/auth` today and
      # it reads `SECRET_KEY` out of the `carmodpicker-<env>/app` secret, not
      # one variable below. Row 5 mounts `webbpulse.identity` and the settings
      # object is built from these; setting them here first is what makes row 5
      # a code change against infrastructure that already exists.
      #
      # Every name is a field of `webbpulse.identity.IdentitySettings`, whose
      # `env_prefix` is `IDENTITY_`, so the composition root builds the settings
      # object straight from the environment with no per-field plumbing. Adding
      # a setting is one line here and none in Python, which is the point of
      # the prefix.
      #
      # THE FIVE VARIABLES THE MODULE OWNS ARE NOT WRITTEN OUT HERE.
      # IDENTITY_ISSUER, IDENTITY_AUDIENCE, IDENTITY_SIGNING_KEY_ARNS,
      # IDENTITY_COOKIE_DOMAIN and IDENTITY_RP_ID, plus IDENTITY_DATA_KEY_ARN,
      # come from `module.identity.identity_environment`, merged LAST at the
      # bottom of this block so that a product override of one of them is
      # impossible rather than merely unlikely. A product override of
      # IDENTITY_ISSUER would be a mismatch between the gateway and the signer
      # that denies every request while logging no reason, and the merge order
      # is what rules it out by construction.
      #
      # IDENTITY_ENVIRONMENT is separate from APP_ENVIRONMENT above even though
      # both carry the same value. IdentitySettings has its own `environment`
      # field under the same prefix and it gates exactly two things: the refusal
      # of a plaintext http issuer, and the local development fallbacks. Letting
      # it default to `local` in a deployed function would silently switch both
      # to their permissive setting, so it is set explicitly.
      name == "identity" ? merge({
        IDENTITY_ENVIRONMENT       = var.environment
        IDENTITY_PRODUCT_NAME      = "CarModPicker"
        IDENTITY_RP_NAME           = "CarModPicker"
        IDENTITY_SUPPORT_EMAIL     = "support@${local.active_domain}"
        IDENTITY_FRONTEND_BASE_URL = local.frontend_url

        # The sender and the configuration set the package's own M3 mail goes
        # out through. Both name what this repository already owns: `ses.tf`
        # creates `aws_sesv2_configuration_set.transactional` and
        # `local.email_from` is the same `no-reply@` address the legacy
        # verification and reset mail already sends from, so identity mail and
        # product mail land in the same configuration set and the same event
        # destinations.
        #
        # An empty IDENTITY_EMAIL_FROM is the package's off switch for its four
        # email routes, and it is deliberately not used here: `local.email_from`
        # coalesces to `no-reply@${local.active_domain}`, which is non-empty in
        # every profile, because this product has a verified SES identity in
        # every environment it deploys to.
        #
        # The frontend link paths are NOT set, because IdentitySettings has no
        # field for them: `/verify-email` and `/reset-password` are module
        # constants in `webbpulse.identity.verification` and the link is built
        # as IDENTITY_FRONTEND_BASE_URL plus the path plus `?token=`. Those two
        # pages are row 6's work; today's reset page is at
        # `/forgot-password/confirm` and needs a route or a redirect.
        IDENTITY_EMAIL_FROM            = local.email_from
        IDENTITY_SES_CONFIGURATION_SET = aws_sesv2_configuration_set.transactional.configuration_set_name

        # ON, and explicitly rather than by omission. The package defaults
        # registration to on and this is one of the two places CarModPicker
        # diverges from Portfolio, which sets it false: Portfolio is a single
        # administrator product whose one account is seeded, and CarModPicker
        # allows public sign up through `POST /api/users/` today. Turning it off
        # would remove a shipped feature at cutover, so it stays on and is
        # written out so that a future reader sees a decision rather than a
        # default.
        IDENTITY_REGISTRATION_ENABLED = "true"
        },

        # The module's own map, merged last so it wins over anything above it.
        # See the note above on why the ordering is load bearing.
      module.identity.identity_environment) : {},
    )
  }
}

variable "bootstrap_image_tag" {
  description = "Image tag used as the seed for every per-domain function, as pushed to ECR by the container image build in deploy-backend.yml. Lambda pulls and optimises the image when it creates the function, so a tag that does not resolve fails the create: the tag named here must already exist in the repository of every domain in local.lambda_domains_declared before the apply. It is only ever a seed, because image_uri is on the lambda-function module's ignore_changes list, so the deploy step's UpdateFunctionCode is not undone by the next plan and this value never needs changing again. The empty string is the bootstrap value for a fresh account that has no images yet: it resolves local.lambda_domains and local.routed_lambda_domains to empty, so the apply builds the repositories and everything else and creates no domain function and cuts no route. See the Promoting to a fresh account section of docs/migration/split-plan.md."
  type        = string
  default     = ""

  validation {
    condition     = var.bootstrap_image_tag == "" || can(regex("^sha-[0-9a-f]{40}$", var.bootstrap_image_tag))
    error_message = "bootstrap_image_tag must be sha- followed by a full 40 character commit sha, which is the tag the container image build pushes, or the empty string to bootstrap an account whose ECR repositories hold no images yet."
  }
}

module "lambda_domain" {
  for_each = local.lambda_domains

  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/lambda-function"
  version = "~> 2.1"

  # `carmodpicker-<env>-<domain>`, which is exactly the key the image map in
  # .github/workflows/deploy-backend.yml builds for UpdateFunctionCode and the
  # name pattern the deploy role's lambda_domain_function_arns already grants
  # on. Changing this shape breaks both without a plan error.
  function_name = "${local.prefix}-${each.key}"
  role_name     = "${local.prefix}-lambda-${each.key}"

  # An Image function takes neither runtime nor handler: the image supplies
  # both, and the module rejects either one alongside package_type = "Image".
  # No image_config either, because the Dockerfile already declares the CMD that
  # starts this domain's entrypoint out of /etc/carmodpicker-entrypoint.
  package_type = "Image"

  # arm64, per section 2.6, which is where the monolith's x86_64 is left behind.
  # Row 11 verified the three native pins on aarch64 (Pillow, bcrypt, webauthn)
  # by building and running all nine images, and `media` is the one that
  # exercises Pillow, which is why the plan cuts it first.
  architectures = ["arm64"]
  memory_size   = each.value.memory

  # 29 seconds, matching the HTTP API integration timeout the routes in row 14
  # will use. A longer function timeout is invisible because the gateway gives
  # up first.
  timeout = 29

  # The seed only. The repository URL comes from module.registry rather than
  # being rebuilt from the account id and the region, so the function and the
  # repository cannot drift to different names.
  code = {
    image_uri = "${module.registry.repository_urls[each.key]}:${var.bootstrap_image_tag}"
  }

  environment_variables = local.lambda_domain_environment[each.key]

  # 7 days, the retention the platform migration decision settled on, and
  # created by Terraform rather than lazily by Lambda so the retention is in
  # place from the first invoke instead of after the group has already collected
  # a run of never expiring events. The monolith stays at 14 until row 17 moves
  # both; this function starts where it is going to end up.
  log_retention_days           = 7
  log_format                   = "JSON"
  application_log_level        = "INFO"
  system_log_level             = "INFO"
  set_logging_config_log_group = true

  # Unlike the monolith, whose runtime policy carried the two X-Ray actions
  # before the module owned them, these roles are new, so the module attaches
  # its own X-Ray write policy and the runtime policy below does not repeat
  # xray:PutTraceSegments or xray:PutTelemetryRecords. It does add
  # xray:PutSpans, which the module's policy does not carry; see the statement
  # below.
  tracing_mode             = "Active"
  attach_xray_write_policy = true

  tags = { Name = "${local.prefix}-${each.key}" }
}

# ---------------------------------------------------------------------------
# One runtime policy per domain, naming only that domain's tables. Section 3.4.
#
# Logs are here, because the module creates the log group but leaves writing to
# it to the application, the same way the monolith's runtime policy does.
#
# X-Ray is here only in part, and row 16 is what put it here. The module's
# attach_xray_write_policy grants xray:PutTraceSegments and
# xray:PutTelemetryRecords, which are the two actions the X-Ray *segment* API
# takes and the two the Lambda service itself needs for Active tracing, so those
# are not repeated. They are not the actions the OTLP endpoint takes:
# `POST https://xray.<region>.amazonaws.com/v1/traces` is authorized by
# xray:PutSpans, and that is the call webbpulse's OTLPAwsSpanExporter makes on
# every flush. Neither the module's inline policy nor the AWS managed
# AWSXrayWriteOnlyAccess carries it, so without the statement below every export
# is a 403, which the exporter retries in silence, and the symptom is that
# traces never appear with nothing in the logs to say why.
#
# xray:PutSpansForIndexing is granted alongside it. Both actions are in the
# X-Ray service authorization reference at Write level, and the pair is what
# Transaction Search indexes a span through; PutSpans alone would export the
# span and leave it unsearchable. Neither action takes a resource-level
# permission, so "*" is the only resource either accepts.
# ---------------------------------------------------------------------------

resource "aws_iam_role_policy" "lambda_domain" {
  for_each = local.lambda_domains

  name = "${each.key}-runtime"
  role = module.lambda_domain[each.key].role_id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid      = "WriteOwnLogs"
          Effect   = "Allow"
          Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
          Resource = "${module.lambda_domain[each.key].log_group_arn}:*"
        },
        {
          Sid      = "WriteSpansToTheXRayOTLPEndpoint"
          Effect   = "Allow"
          Action   = ["xray:PutSpans", "xray:PutSpansForIndexing"]
          Resource = "*"
        },
      ],
      length(local.lambda_domain_write_arns[each.key]) > 0 ? [
        {
          Sid      = "ReadWriteOwnTables"
          Effect   = "Allow"
          Action   = local.dynamodb_domain_write_actions
          Resource = local.lambda_domain_write_arns[each.key]
        },
      ] : [],
      length(local.lambda_domain_read_arns[each.key]) > 0 ? [
        {
          Sid      = "ReadSharedTables"
          Effect   = "Allow"
          Action   = local.dynamodb_domain_read_actions
          Resource = local.lambda_domain_read_arns[each.key]
        },
      ] : [],
      # The one app secret, and only for the domains that read it. `media`'s
      # descriptor in app/composition/domains.py declares
      # requires_secrets=("SECRET_KEY",), because all eight of its routes verify
      # a token, and SECRET_KEY is a key of the carmodpicker-<env>/app JSON.
      #
      # Written out rather than taken from module.app_secrets.read_policy_statement,
      # which Portfolio uses, because that output's policy_actions default is the
      # pair GetSecretValue and DescribeSecret. Section 3.4 names one action and
      # the monolith's runtime policy grants one action, so this grants one
      # action. The resource still comes off the module, so the policy cannot
      # name a secret the module does not create.
      each.value.secrets ? [
        {
          Sid      = "ReadTheAppSecret"
          Effect   = "Allow"
          Action   = ["secretsmanager:GetSecretValue"]
          Resource = [module.app_secrets.arns["app"]]
        },
      ] : [],
      # The user images bucket. The object actions and the bucket action are two
      # statements because they take different resources: an object action is
      # authorized against `<bucket>/*` and ListBucket against the bucket ARN
      # itself, so folding them together would grant neither what it needs.
      #
      # Section 3.4 lists five actions here and this grants four, and the
      # difference is a correction rather than a reduction. `s3:HeadObject` is
      # not an IAM action: it does not appear in AWS's own machine readable
      # service reference for S3, and the HeadObject API is authorized by
      # `s3:GetObject`, which is already granted above. IAM accepts an action
      # name that matches nothing without complaint, so the monolith's policy in
      # lambda.tf carries both `s3:HeadObject` and `s3:HeadBucket` today and
      # neither has ever granted anything; only Access Analyzer's advisory
      # ValidatePolicy flags them, and nothing in the pipeline runs it. Carrying
      # them forward would make this policy look broader than it is, which is
      # the opposite of what a per-domain split is for. Cleanup for a later
      # pass: drop the same two from the monolith's user_images_rw document.
      #
      # `s3:ListBucket` is doing two jobs. It authorizes list_objects_v2, which
      # the orphan sweep pages through, and it is also what authorizes
      # head_bucket, the call StorageService.__init__ makes once per cold start
      # to decide whether uploads are enabled at all. Without it the service
      # disables itself silently and every upload route answers as if the bucket
      # were unconfigured, with a warning in the logs and no error to the caller.
      #
      # `s3_delete_only` is row 26's narrowing. Every entry declares it, because
      # `local.lambda_domains` is a conditional whose other branch is the empty
      # map: Terraform requires both branches of a conditional to have a
      # consistent type, so an attribute present on one entry only fails the
      # validate rather than defaulting. `build-lists`
      # makes exactly one S3 call, `delete_image` from the gallery delete route,
      # so it gets `s3:DeleteObject` and not the other two: it has no upload
      # route, and it reads image keys out of its own DynamoDB row rather than
      # out of the bucket. `s3:ListBucket` is granted either way, because it is
      # what authorizes the `head_bucket` in `StorageService._ensure_client`
      # and, without it, `delete_image` returns False and the object is orphaned
      # while the row loses its key.
      each.value.s3 ? [
        {
          Sid    = each.value.s3_delete_only ? "DeleteUserImageObjects" : "ReadWriteUserImageObjects"
          Effect = "Allow"
          Action = each.value.s3_delete_only ? [
            "s3:DeleteObject",
            ] : [
            "s3:PutObject",
            "s3:GetObject",
            "s3:DeleteObject",
          ]
          Resource = ["${aws_s3_bucket.user_images.arn}/*"]
        },
        {
          Sid      = "ListTheUserImagesBucket"
          Effect   = "Allow"
          Action   = ["s3:ListBucket"]
          Resource = [aws_s3_bucket.user_images.arn]
        },
      ] : [],
      # Section 3.4's SES split, `identity`'s half of it, arriving with the two
      # routes that send. Row 27. The statement is character for character the
      # one `lambda_stream_consumers.tf` gives the price alert consumer, and the
      # reasoning behind each half of the resource list is recorded there in
      # full rather than repeated here:
      #
      #   - Both resources are required rather than either. SESv2 `SendEmail`
      #     authorizes against the sending identity and, because
      #     `app/core/email.py` passes `ConfigurationSetName`, against the
      #     configuration set as well, so naming one fails the send with an
      #     AccessDenied that reads as if the other were missing.
      #   - `identity/*` rather than a single identity ARN, because
      #     `local.custom_domain` decides whether the verified identity is the
      #     domain or the bare sender mailbox and those are two different
      #     resources under mutually exclusive counts. The wildcard is scoped to
      #     this account and this region by the ARN itself and the account holds
      #     one SES identity, so what it widens to is nothing.
      #   - `SendRawEmail` is not granted. `_send` calls `sesv2:SendEmail` and
      #     nothing in this image composes a raw MIME message. The monolith
      #     carries the action only because its policy predates the SESv2 client.
      #
      # The one thing that is genuinely this row's rather than row 25's is what
      # happens without it. `admin`'s send was a fire and forget whose failure
      # left `last_fired_at` alone for the next observation to retry, so the
      # grant could wait for the code. Here both callers are written as
      # `if not send_...(...): raise_internal_server_error(...)`, so a missing
      # grant is a 500 on email verification and on password reset rather than a
      # silent no-op, and the grant cannot wait.
      each.value.ses ? [
        {
          Sid    = "SendTransactionalMail"
          Effect = "Allow"
          Action = ["ses:SendEmail"]
          Resource = [
            "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:identity/*",
            "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:configuration-set/${aws_sesv2_configuration_set.transactional.configuration_set_name}",
          ]
        },
      ] : [],
    )
  })
}
