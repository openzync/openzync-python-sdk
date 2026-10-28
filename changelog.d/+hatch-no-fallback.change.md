Removed the silent `"0.0.0"` version fallback; missing package metadata now raises `RuntimeError` so a broken install fails loudly instead of misidentifying the client via User-Agent headers.
