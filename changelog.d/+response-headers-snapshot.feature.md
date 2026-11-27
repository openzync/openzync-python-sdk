Added a `last_response_headers` snapshot on the async transport, exposing the lowercased headers of the most recent HTTP response (returned as a copy, so later requests cannot mutate it).
