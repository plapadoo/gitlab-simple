let
  bootstrap = import <nixpkgs> { };

  nixpkgs = builtins.fromJSON (builtins.readFile ./nixpkgs.json);

  src = bootstrap.fetchFromGitHub {
    owner = "NixOS";
    repo  = "nixpkgs-channels";
    inherit (nixpkgs) rev sha256;
  };

  pkgs = import src { };

  packageOverrides = self: super: {
    python-gitlab = super.buildPythonPackage rec {
      pname  = "python-gitlab";
      version = "1.6.0";

      src = self.fetchPypi {
        sha256 = "15g77mvkaw6si9f7pmb1a9sx04wh0fsscmj0apk2qhcs5wivkki0";
        inherit pname version;
      };

      doCheck = false;

      propagatedBuildInputs = [ super.six super.requests ];
    };
  };

  python = pkgs.python3.override { inherit packageOverrides; };

  pythonPkgs = python.pkgs;

  repoSrc = ./.;
in
  pythonPkgs.buildPythonApplication rec {
    name = "gitlab-simple";

    version = "1.0";

    src = repoSrc;

    propagatedBuildInputs = [
      pythonPkgs.python-gitlab
      pythonPkgs.pyxdg
    ];

    doCheck = false;

    buildInputs = [
      pkgs.python3
      pythonPkgs.ipython
      pythonPkgs.ipdb
      pythonPkgs.pylint
      pythonPkgs.mypy
      pythonPkgs.yapf
    ];
  }
