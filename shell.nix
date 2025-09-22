{ pkgs ? import <nixpkgs> { } }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python313
    python313Packages.flet-desktop
    python313Packages.flet-web
    kdePackages.kdialog # filepicker
    cacert
  ];
  shellHook = ''
    export SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt
    export NIX_SSL_CERT_FILE=$SSL_CERT_FILE
    source ~/.zsh_aliases
    source ~/Documents/DocSync/Python/DocTemplater/.venv/bin/activate
  '';
}

