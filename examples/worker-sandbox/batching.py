"""Small development-worker fixture: split an ordered job list into batches."""


def batch_items(items, capacity):
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
        raise ValueError("capacity must be a positive integer")
    return [items[start:start + capacity] for start in range(0, len(items), capacity)]
