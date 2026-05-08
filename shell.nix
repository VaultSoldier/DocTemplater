{ pkgs ? import <nixpkgs> { } }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python314
    # python313Packages.flet-desktop
    # python313Packages.flet-web
    git
    cmake
    clang
    ninja
    pkg-config
    kdePackages.kdialog # filepicker
    cacert
    which
    gtk3
    cairo
    glib
    sysprof
    fontconfig
    libepoxy
    dbus
  ];

  LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
    pkgs.gtk3
    pkgs.glib
    pkgs.sysprof
    pkgs.cairo
    pkgs.fontconfig
    pkgs.libepoxy
    pkgs.dbus
  ];
  shellHook = ''
    # export SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt
    # export NIX_SSL_CERT_FILE=$SSL_CERT_FILE
    source ~/.config/zsh/zsh_aliases
    source ~/Projects/Python/DocTemplater/.venv/bin/activate
  '';
}

