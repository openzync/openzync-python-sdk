Normalize OPENZYNC_ALLOWED_HOSTS entries (strip ports, brackets, case) so allowlisted hosts with ports match, and reject http(s) base URLs with an empty host loudly instead of skipping validation.
