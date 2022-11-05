with (import <nixpkgs> {});

pkgs.mkShell {
    buildInputs = [
      python310
      python310Packages.venvShellHook
      nodejs-16_x
    ];

    venvDir = "./.nix-venv";

    postShellHook = ''
      ./.nix-venv/bin/pip install --quiet -Iv eth-brownie==1.19.1
      ./.nix-venv/bin/pip install --quiet -r ./requirements.txt
      export PYTHONPATH=$PYTHONPATH:$(pwd)/lib:$(pwd)/scripts:$(pwd)/brownie
    '';
}
