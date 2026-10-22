"""A real application calling the emitted Python module."""
import attachment as bridge
values = [2,3,5,7]
assert bridge.omega_total(values,4) == (0,17)
data = bytearray([1,2,254,255])
assert bridge.omega_bump(data,4) == (0,0)
assert list(data) == [2,3,255,0]
assert bridge.omega_narrow(256) == (5,None)
assert bridge.omega_divide(9,0) == (2,None)
assert bridge.omega_total(values,3) == (8,None)
assert bridge.omega_total(None,4) == (8,None)
assert bridge.omega_total(values,4) == (0,17)
assert bridge.omega_copy(values,4,values,4) == (8,None)
assert bridge.omega_copy(values,4,[11,13,17,19],4) == (0,0)
assert values == [11,13,17,19]
print('Python caller: values, mutation, traps, invalid lengths and recovery OK')
