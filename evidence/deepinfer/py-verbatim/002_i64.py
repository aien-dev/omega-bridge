def i64(x: int) -> int:
    return x if x < 0x8000000000000000 else x - 0x10000000000000000
