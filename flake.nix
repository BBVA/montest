{
  description = "montest development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachSystem [
      "aarch64-linux"
      "x86_64-linux"
      "aarch64-darwin"
      "x86_64-darwin"
    ] (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pkgs.uv
            pkgs.python311
            pkgs.python312
            pkgs.python313
            pkgs.python314
          ];

          shellHook = ''
            echo "montest dev environment ready"
            echo "  uv:        $(uv --version)"
            echo "  python3.11: $(python3.11 --version)"
            echo "  python3.12: $(python3.12 --version)"
            echo "  python3.13: $(python3.13 --version)"
            echo "  python3.14: $(python3.14 --version)"
          '';
        };
      });
}
