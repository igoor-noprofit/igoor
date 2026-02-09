# hook-sklearn.py
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = collect_all('sklearn')

# Add specific Cython modules that are often missed
hiddenimports += [
    'sklearn.utils._cython_blas',
    'sklearn.neighbors.typedefs',
    'sklearn.neighbors.quad_tree',
    'sklearn.tree',
    'sklearn.tree._tree',
    'sklearn.tree._utils',
    'sklearn.utils._weight_vector',
    'sklearn.utils._logistic_sigmoid',
    'sklearn.neighbors._partition_nodes',
]

# Collect all submodules
hiddenimports += collect_submodules('sklearn')