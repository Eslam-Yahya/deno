#!/usr/bin/env python
import third_party
from util import build_mode, build_path, enable_ansi_colors, root_path, run
from util import shell_quote
import os
import re
import sys
from distutils.spawn import find_executable


def main():
    enable_ansi_colors()

    os.chdir(root_path)

    third_party.fix_symlinks()
    third_party.download_gn()
    third_party.download_clang_format()
    third_party.download_clang()
    third_party.maybe_download_sysroot()

    write_lastchange()

    mode = build_mode(default=None)
    if mode is not None:
        gn_gen(mode)
    else:
        gn_gen("release")
        gn_gen("debug")


def write_if_not_exists(filename, contents):
    if not os.path.exists(filename):
        with open(filename, "w+") as f:
            f.write(contents)


def write_lastchange():
    write_if_not_exists(
        "build/util/LASTCHANGE",
        "LASTCHANGE=c42e4ddbb7973bfb0c57a49ab6bf6dc432baad7e-\n")
    write_if_not_exists("build/util/LASTCHANGE.committime", "1535518087")
    # TODO Properly we should call the following script, but it seems to cause
    # a rebuild on every commit.
    # run([
    #    sys.executable, "build/util/lastchange.py", "-o",
    #    "build/util/LASTCHANGE", "--source-dir", root_path, "--filter="
    # ])


# If this text is found in args.gn, we assume it hasn't been hand edited.
gn_args_header = [
    "# This file is automatically generated by tools/setup.py.",
    "# REMOVE THIS LINE to preserve any changes you make.", ""
]


def gn_string(s):
    # In gn, strings are enclosed in double-quotes and use backslash as the
    # escape character. The only escape sequences supported are:
    #   \" (for literal quote)
    #   \$ (for literal dollars sign)
    #   \\ (for literal backslash)
    # Any other use of a backslash is treated as a literal backslash.
    s = re.sub(r'("|\$|\\(?=["$\\]))', r'\\\1', s)
    s = '"' + s + '"'
    return s


def gn_args_are_generated(lines):
    for line in lines:
        if re.match("^\s*#.*REMOVE THIS LINE", line):
            return True
    return False


def read_gn_args(args_filename):
    if not os.path.exists(args_filename):
        return (None, False)  # No content, not hand edited.

    with open(args_filename) as f:
        lines = f.read().splitlines()
        args = [l.strip() for l in lines if not re.match("^\s*(#|$)", l)]
        hand_edited = not gn_args_are_generated(lines)
        return (args, hand_edited)


def write_gn_args(args_filename, args):
    assert not gn_args_are_generated(args)  # No header -> hand crafted.
    lines = gn_args_header + args
    assert gn_args_are_generated(lines)  # With header -> generated.

    # Ensure the directory where args.gn goes exists.
    dir = os.path.dirname(args_filename)
    if not os.path.isdir(dir):
        os.makedirs(dir)

    with open(args_filename, "w") as f:
        f.write("\n".join(lines) + "\n")


def generate_gn_args(mode):
    out = []
    if mode == "release":
        out += ["is_official_build=true"]
    elif mode == "debug":
        pass
    else:
        print "Bad mode {}. Use 'release' or 'debug' (default)" % mode
        sys.exit(1)

    if "DENO_BUILD_ARGS" in os.environ:
        out += os.environ["DENO_BUILD_ARGS"].split()

    # Check if ccache or sccache are in the path, and if so we set cc_wrapper.
    cc_wrapper = find_executable("sccache") or find_executable("sccache")
    if cc_wrapper:
        # The gn toolchain does not shell escape cc_wrapper, so do it here.
        out += ['cc_wrapper=%s' % gn_string(shell_quote(cc_wrapper))]
        # For cc_wrapper to work on Windows, we need to select our own toolchain
        # by overriding 'custom_toolchain' and 'host_toolchain'.
        # TODO: Is there a way to use it without the involvement of args.gn?
        if os.name == "nt":
            tc = "//build_extra/toolchain/win:win_clang_x64"
            out += ['custom_toolchain="%s"' % tc, 'host_toolchain="%s"' % tc]

    # Look for sccache; if found, set rustc_wrapper.
    rustc_wrapper = find_executable("sccache")
    if rustc_wrapper:
        out += ['rustc_wrapper=%s' % gn_string(rustc_wrapper)]

    return out


# gn gen.
def gn_gen(mode):
    os.environ["DENO_BUILD_MODE"] = mode

    # Rather than using gn gen --args we write directly to the args.gn file.
    # This is to avoid quoting/escaping complications when passing overrides as
    # command-line arguments.
    args_filename = os.path.join(build_path(), "args.gn")

    # Check if args.gn exists, and if it was auto-generated or handcrafted.
    existing_gn_args, hand_edited = read_gn_args(args_filename)

    # If args.gn wasn't handcrafted, regenerate it.
    if hand_edited:
        print "%s: Using gn options from hand edited '%s'." % (mode,
                                                               args_filename)
        gn_args = existing_gn_args
    else:
        print "%s: Writing gn options to '%s'." % (mode, args_filename)
        gn_args = generate_gn_args(mode)
        if gn_args != existing_gn_args:
            write_gn_args(args_filename, gn_args)

    for line in gn_args:
        print "  " + line

    run([third_party.gn_path, "gen", build_path()],
        env=third_party.google_env())


if __name__ == '__main__':
    sys.exit(main())
