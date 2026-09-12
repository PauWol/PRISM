from prism.foundation.constants import EXTERNAL_DEPENDENCIES
from prism.setup.installer import Installer


class Doctor:
    def __init__(self) -> None:
        self._installer: Installer = Installer()

    @staticmethod
    def _print_missing_dependencies(missing: list[str]):
        if len(missing) == 0:
            return

        print("Following external dependencies are missing:")
        for m in missing:
            print(f"  - {m}\n")

        print("\n\n")

    def _detect_missing_system_dependencies(self) -> list[str]:
        _missing: list[str] = []

        for dep in EXTERNAL_DEPENDENCIES:
            if self._installer.is_installed(dep):
                continue

            _missing.append(dep)

        return _missing

    def _install_missing(self, missing: list[str]):
        for dep in missing:
            if not self._installer.install(dep):
                print(f"Couldn't install: {dep}!")

    def run(self, autofix: bool = False):

        _missing_ext_deps = self._detect_missing_system_dependencies()
        self._print_missing_dependencies(_missing_ext_deps)
        if autofix:
            self._install_missing(_missing_ext_deps)
