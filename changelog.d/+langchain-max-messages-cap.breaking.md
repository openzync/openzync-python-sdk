Default `max_messages` to 500 and clamp any larger value to the backend's `le=500` limit — callers relying on the previous 1000 default now receive 500 messages.
