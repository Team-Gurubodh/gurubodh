"""Check the PyTorch wheel selected by the supported native CLI install."""

import argparse
import platform


def expected_version():
    system, machine = platform.system(), platform.machine()
    if system == "Darwin" and machine == "x86_64":
        return "2.2.2"
    if (system, machine) in {
        ("Darwin", "arm64"), ("Linux", "x86_64"), ("Linux", "aarch64")
    }:
        return "2.5.1"
    raise SystemExit(f"Unsupported CLI install platform: {system} {machine}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-version", action="store_true")
    args = parser.parse_args()
    expected = expected_version()
    if args.expected_version:
        print(expected)
        return

    import torch

    actual = torch.__version__
    if actual not in (expected, expected + "+cpu"):
        raise SystemExit(f"Expected CPU PyTorch {expected}, found {actual}")
    if torch.version.cuda is not None:
        raise SystemExit(f"CUDA runtime found: {torch.version.cuda}")
    if torch.cuda.is_available():
        raise SystemExit("CUDA is available in the installed runtime")
    print(f"PyTorch {actual} on {platform.system()} {platform.machine()}; CUDA runtime absent")


if __name__ == "__main__":
    main()
