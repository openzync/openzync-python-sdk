Validate dict messages through `Message` in `_as_message`, so a bad role fails locally with `ValidationError` instead of a server 422 round-trip.
