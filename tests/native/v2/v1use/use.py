# Imports the v1 binding (it looks up omega_bsum at import) beside the v2 library: must fail.
import sys
sys.path.insert(0, sys.argv[1])
import omega_native
print("imported")
