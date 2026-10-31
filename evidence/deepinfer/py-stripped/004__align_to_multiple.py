def align_to_multiple(numerator, denominator, alignment):
    return (numerator + denominator * alignment - 1) // (denominator * alignment) * alignment
