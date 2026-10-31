def _align_to_multiple(numerator: int, denominator: int, alignment: int) -> int:
    """把 numerator 个元素按每 denominator 个一组分组后，组数向上对齐到 alignment 的倍数。denominator=1 时即普通向上对齐。"""
    return (numerator + denominator * alignment - 1) // (denominator * alignment) * alignment
