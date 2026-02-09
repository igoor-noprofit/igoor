# hook-numpy.py
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

# Collect all numpy binaries (C extensions)
binaries = collect_dynamic_libs('numpy')

# Collect critical numpy submodules
hiddenimports = collect_submodules('numpy')

# Explicitly add commonly missed modules
hiddenimports += [
    'numpy.core._multiarray_umath',
    'numpy.core._multiarray_tests',
    'numpy.core.multiarray',
    'numpy.core._dtype_ctypes',
    'numpy.core._internal',
    'numpy.random',
    'numpy.random.common',
    'numpy.random.bounded_integers',
    'numpy.random.entropy',
]

datas = []