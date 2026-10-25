Fixed SDK retry and error mapping diverging between request and request_multipart; both now share one _send_with_retry helper so the fix applies once.
