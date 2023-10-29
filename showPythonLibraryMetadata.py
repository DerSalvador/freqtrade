import sys
import importlib
import importlib.metadata
i=importlib
print("############################################\n")
print("Library Module Search Path\n")
print(i.sys.path)
print("############################################\n")
print("Involved files in Libary: " + sys.argv[1] + "\n")
imp=importlib.metadata
print(imp.files(sys.argv[1]))
