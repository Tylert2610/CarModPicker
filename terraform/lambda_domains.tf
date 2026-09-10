# ---------------------------------------------------------------------------
# The per-domain FastAPI functions, delivered as container images and run under
# the AWS Lambda Web Adapter. Section 3.3 and section 3.4 of
# docs/migration/split-plan.md, row 13 of section 8.
#
# `media` from row 13, `build-logs` from row 18, `moderation` from row 19,
# `vehicles` from row 20, `admin` from row 21 and `build-lists` from row 26 are
# the entries today. Rows 27 through 31 add the other three, one per row, and
# the shape here is built
# for that: everything a domain needs is one entry in `local.lambda_domains`,
# and the module call, the IAM policy and the outputs all key off it, so adding
# a domain is adding a map entry.
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
  # `s3` is whether the function gets the user images bucket at all, and
  # `s3_delete_only` narrows what it gets when it does. Section 3.4 names
  # `media` and, from row 31, `users`: the full set including ListBucket for
  # `media` and the three object actions for avatars for `users`.
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
  #     None of these is a seam this row unwinds. Section 1.3's seams 1, 2 and 4
  #     are what eventually narrow this list, and rows 25, 28 and 30 are where
  #     they land. Until then the grant follows the writer, and the writer is
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
  lambda_domains_declared = {
    media = {
      secrets        = true
      s3             = true
      s3_delete_only = false
      memory         = 512
      tables         = ["image_source_mappings", "rate-limits"]
      read_tables    = ["users", "car_generations", "parts", "build_lists"]
    }
    build-logs = {
      secrets        = true
      s3             = false
      s3_delete_only = false
      memory         = 256
      tables         = ["build_log_posts", "rate-limits"]
      read_tables    = ["users", "build_lists", "build_logs"]
    }
    moderation = {
      secrets        = true
      s3             = false
      s3_delete_only = false
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
      memory         = 256
      # Fifteen written tables, fourteen of them real and the fifteenth the
      # limiter's counter. This is the widest write list of the nine by a wide
      # margin, and it is the domain's whole purpose rather than a failure to
      # narrow it: the two admin modules seed and purge six domains' tables by
      # design. The derivation above names the call behind every one.
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
        "build_list_parts",
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
  # probe the prefix, find routeKey "$default", and exit 1. Gating both sets on
  # the same condition is what keeps that middle state from existing.
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
  #     `admin`'s, per section 3.4's SES split. No domain function cut so far
  #     sends mail, `admin` included: its one mail path is the price-drop alert,
  #     which is called from `catalog`'s price capture rather than from any
  #     route this domain serves, and seam 4 is what moves it. A configured
  #     sender on a function with no ses:SendEmail grant is a misleading
  #     configuration, so the key waits for the code.
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
      domain.s3 ? {
        USER_IMAGES_BUCKET = aws_s3_bucket.user_images.bucket
        # Empty means "the real S3 endpoint". The monolith filters empty values
        # out of its map for this key; here it is simply not set, which is the
        # same thing to pydantic and one fewer moving part.
      } : {},
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
    )
  })
}
