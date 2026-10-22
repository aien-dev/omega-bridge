/* SPDX-License-Identifier: AGPL-3.0-only */
/* Detection is independent of attachment qualification. No production hooks
 * yet. */
struct descriptor {
  const char *name, *language, *version_arg;
};
static const struct descriptor registry[] = {
    {"python", "python", "--version"},
    {"python3", "python", "--version"},
    {"node", "node", "--version"},
    {"nodejs", "node", "--version"},
    {"rustc", "rust", "--version"},
    {"go", "go", "version"},
    {"java", "jvm", "-version"},
    {"javac", "jvm", "-version"},
    {"dotnet", "dotnet", "--version"},
    {"ruby", "ruby", "--version"},
    {"php", "php", "--version"},
    {"cc", "c", "--version"},
    {"gcc", "c", "--version"},
    {"clang", "c", "--version"},
    {"c++", "cpp", "--version"},
    {"g++", "cpp", "--version"},
    {"clang++", "cpp", "--version"},
    {"swift", "swift", "--version"},
    {"julia", "julia", "--version"},
    {"lua", "lua", "-v"},
    {"luajit", "lua", "-v"},
    {"perl", "perl", "--version"},
    {"R", "r", "--version"},
    {"Rscript", "r", "--version"},
    {"zig", "zig", "version"},
    {"elixir", "elixir", "--version"},
    {"erl", "erlang", "-version"},
    {"ghc", "haskell", "--version"},
    {"ocaml", "ocaml", "-version"},
    {"dart", "dart", "--version"},
    {"deno", "deno", "--version"},
    {"bun", "bun", "--version"},
#ifdef OMEGA_ATTACH_TESTING
    {"omega-fixture", "fixture", "--version"},
#endif
};
static const char *manager_vars[] = {
    "VIRTUAL_ENV",   "WORKON_HOME",  "PYENV_ROOT",  "CONDA_PREFIX", "NVM_DIR",
    "VOLTA_HOME",    "RUSTUP_HOME",  "CARGO_HOME",  "GOROOT",       "GOPATH",
    "JAVA_HOME",     "SDKMAN_DIR",   "DOTNET_ROOT", "RBENV_ROOT",   "RVM_PATH",
    "ASDF_DATA_DIR", "MISE_DATA_DIR"};
static const char *manager_defaults[]
    __attribute__((unused)) = {".virtualenvs",
                               ".local/share/virtualenvs",
                               ".pyenv/versions",
                               ".conda/envs",
                               "miniconda3",
                               "anaconda3",
                               "miniforge3",
                               ".local/share/conda",
                               ".nvm/versions/node",
                               ".local/share/fnm/node-versions",
                               ".volta/bin",
                               ".rustup/toolchains",
                               ".cargo/bin",
                               "go/bin",
                               ".go/bin",
                               ".sdkman/candidates",
                               ".dotnet",
                               ".rbenv/versions",
                               ".rvm/rubies",
                               ".asdf/installs",
                               ".local/share/mise/installs"};
