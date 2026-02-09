from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = collect_all('sentence_transformers')

# Also collect transformers since sentence_transformers depends on it
datas_t, binaries_t, hiddenimports_t = collect_all('transformers')
datas += datas_t
binaries += binaries_t
hiddenimports += hiddenimports_t

# Collect torch components
hiddenimports += collect_submodules('torch')