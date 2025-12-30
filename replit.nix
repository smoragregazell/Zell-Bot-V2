{ pkgs }: {
  deps = [
    pkgs.sqlite-interactive
    pkgs.taskflow
    pkgs.rapidfuzz-cpp
    pkgs.rustc
    pkgs.libiconv
    pkgs.cargo
    pkgs.glibcLocales
    pkgs.libxcrypt
    pkgs.python3Packages.asyncpg
  ];
}
