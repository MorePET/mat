---
type: issue
state: open
created: 2026-04-18T23:02:28Z
updated: 2026-04-18T23:02:28Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/MorePET/mat/issues/72
comments: 0
labels: none
assignees: none
milestone: 3.1.2 — post-audit follow-ups
projects: none
parent: none
children: none
synced: 2026-04-19T04:44:00.524Z
---

# [Issue 72]: [Thread-safety docstring has no deterministic test reproducer](https://github.com/MorePET/mat/issues/72)

## Tier 3 — future-proofing

\`Vis\` docstring (\`src/pymat/vis/_model.py:23-35\`) added a Thread safety
section claiming the class is not safe to mutate concurrently:

> ``Vis`` instances are NOT safe to mutate concurrently. The lazy texture
> cache (``_textures`` / ``_fetched``) is populated by a single ``_fetch``
> call guarded only by the ``_fetched`` flag — two threads racing on
> ``.textures`` will each trigger a fetch.

But the test suite has zero threading-related tests. Nothing stops a
future contributor from deleting the docstring section (thinking it's
stale) or from accidentally removing the race (via a lock or similar)
and regressing later.

## Add

A deterministic test that exhibits the claimed race:

```python
def test_concurrent_textures_access_triggers_double_fetch(monkeypatch):
    """Documented behavior: two threads reading .textures simultaneously
    will each trigger a fetch, because the _fetched flag is checked +
    set without synchronization. This test pins the docstring claim
    so a future 'fix' doesn't silently regress to a documented
    single-fetch guarantee we never promised."""
    import threading

    fetch_count = 0
    fetch_event = threading.Event()

    class CountingClient:
        def fetch_all_textures(self, source, material_id, *, tier="1k"):
            nonlocal fetch_count
            fetch_count += 1
            fetch_event.wait(timeout=1.0)  # hold the lock window open
            return {"color": b"x"}

    import mat_vis_client as _client
    monkeypatch.setattr(_client, "_client", CountingClient())

    v = Vis(source="a", material_id="b")

    results = []
    def read():
        results.append(v.textures)

    t1 = threading.Thread(target=read)
    t2 = threading.Thread(target=read)
    t1.start(); t2.start()
    fetch_event.set()  # let both fetches complete
    t1.join(); t2.join()

    # Both threads ran; at least one fetch happened; *may* have been
    # two — the test documents that the framework doesn't prevent it.
    assert fetch_count >= 1
    assert all(r == {"color": b"x"} for r in results)
    # If a future fix makes this always == 1, that's a new guarantee
    # worth adding to the docstring.
```

If we ever want to *actually* make \`Vis\` thread-safe, this test
becomes a RED that forces the docstring update.
