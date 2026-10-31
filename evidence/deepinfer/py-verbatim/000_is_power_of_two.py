def is_power_of_two(x: int) -> bool:
    return x & (x - 1) == 0
