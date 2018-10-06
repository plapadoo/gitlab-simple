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
    commonmark = super.buildPythonPackage rec {
      pname  = "commonmark";
      version = "0.8.0";

      src = self.fetchPypi {
        sha256 = "1kqcqizd8cf61pbb6gcwp1kv6ghw9kzydw99awsmiqx08fy5r8wn";
        inherit pname version;
      };

      doCheck = false;

      propagatedBuildInputs = [ super.future ];
    };
    consolemd = super.buildPythonPackage rec {
      pname  = "consolemd";
      version = "0.4.3";

      src = self.fetchPypi {
        sha256 = "0mcggkyhnzxyalqljd4a5650x8phwnslvkpgbj04cbxcf5888cjz";
        inherit pname version;
      };

      doCheck = false;

      propagatedBuildInputs = [ super.pytestrunner super.click super.pygments self.commonmark super.setproctitle ];
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
      pythonPkgs.terminaltables
      pythonPkgs.termcolor
      pythonPkgs.humanize
      pythonPkgs.python-dateutil
      pythonPkgs.pyxdg
      pythonPkgs.consolemd
    ];

    doCheck = false;

    buildInputs = [
      pkgs.python3
      pythonPkgs.ipython
      pythonPkgs.ipdb
      pythonPkgs.pylint
      pythonPkgs.pyflakes
      pythonPkgs.mypy
      pythonPkgs.black
    ];
  }
