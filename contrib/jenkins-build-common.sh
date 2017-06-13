#!source_this_file

# Common parts for osmo-gsm-tester jenkins build scripts. Use like in below example:
#
#--------------
# #!/bin/sh
# set -e -x
# base="$PWD"
# name="osmo-name"
# . "$(dirname "$0")/jenkins-build-common.sh"
#
# build_repo libosmocore --configure --opts
# build_repo libosmo-foo special_branch --configure --opts
# build_repo osmo-bar
#
# create_bin_tgz
#--------------
#
# Some explanations:
#
# To allow calling from arbitrary working directories, other scripts should
# source this file like shown above.
#
# Sourcing scripts must provide some variables/functions, see above.
# In addition, these values can optionally be passed to override:
# git_url, prefix, prefix_real, BUILD_NUMBER
#
# CONFIGURE_FLAGS may contain flags that should be passed to all builds'
# ./configure steps (useful e.g. for building in the sysmobts SDK).
#
# For each built repository, a specific git branch or hash can be provided by
# environment variable: OSMO_GSM_TESTER_BUILD_$repo="<git-hash>"
# NOTE: convert $repo's dashes to underscore. For example:
#  OSMO_GSM_TESTER_BUILD_osmo_hlr="f001234abc"
#  OSMO_GSM_TESTER_BUILD_libosmocore="my/branch"
# ("origin/" is prepended to branch names automatically)

if [ -z "$name" -o -z "$base" ]; then
  set +x
  echo "Some environment variables are not provided as required by jenkins-build-common.sh. Error."
  exit 1
fi

git_url="${git_url-"git://git.osmocom.org"}"
prefix="${prefix-"$base/inst-$name"}"
# prefix_real is usually identical with prefix, except when installing to a
# different $DESTDIR than /, which is the case for example when building
# osmo-bts within the sysmoBTS SDK
prefix_real="${prefix_real-"$prefix"}"

export PKG_CONFIG_PATH="$prefix_real/lib/pkgconfig:$PKG_CONFIG_PATH"
export LD_LIBRARY_PATH="$prefix_real/lib:$LD_LIBRARY_PATH"

# Show current environment. Sometimes the LESS_ vars have ansi colors making a
# mess, so exclude those.
env | grep -v "^LESS" | sort

# clean the workspace
rm -f "$base/${name}"*.tgz rm -f "$base/${name}"*.md5
rm -rf "$prefix_real"
mkdir -p "$prefix_real"

have_repo() {
  repo="$1"
  branch="${2-master}"

  # Evaluate environment for instructions to build a specific git hash.
  # Using a hash as $branch above unfortunately doesn't work.
  branch_override_var="$(echo "OSMO_GSM_TESTER_BUILD_$repo" | sed 's/-/_/g')"
  branch_override="$(eval "echo \$$branch_override_var")"
  if [ -n "$branch_override" ]; then
    branch="$branch_override"
  fi

  cd "$base"
  if [ ! -d "$repo" ]; then
    git clone "$git_url/$repo" "$repo"
  fi
  cd "$repo"
  rm -rf *
  git fetch origin

  # Figure out whether we need to prepend origin/ to find branches in upstream
  if ! git rev-parse "$branch"; then
    branch="origin/$branch"
  fi

  git reset --hard "$branch"

  git rev-parse HEAD

  cd "$base"
}

build_repo() {
  # usage: build_repo <name> [<branch>] [--configure-opts [...]]
  dep="$1"
  branch="master"
  if [ -z "$(echo "$2" | grep '^-')" ]; then
    # second arg does not start with a dash, it's empty or a branch
    branch="$2"
    if [ -n "$branch" ]; then
      # we had a branch arg, need to shift once more to get config options
      shift
    else
      branch="master"
    fi
  fi
  shift
  configure_opts="$@"

  set +x; echo "

====================== $dep

"; set -x


  have_repo "$dep" "$branch"

  cd "$dep"

  echo "$(git rev-parse HEAD) $dep" >> "$prefix_real/${name}_git_hashes.txt"

  # special shim: we know the openbsc.git needs to be built in the openbsc/ subdir.
  if [ "$dep" = "openbsc" ]; then
    cd openbsc
  fi

  set +x; echo; echo; set -x
  autoreconf -fi
  set +x; echo; echo; set -x
  ./configure --prefix="$prefix" $CONFIGURE_FLAGS $configure_opts
  set +x; echo; echo; set -x
  make -j8 || make  # libsmpp34 can't build in parallel
  set +x; echo; echo; set -x
  make install
}

create_bin_tgz() {
  # don't package documentation -- the libosmocore docs can be up to 16 Mb large,
  # a significant amount compared to the binaries
  rm -rf "$prefix_real/share/doc/{libosmocore,libosmo-sccp}" || true

  # build the archive that is going to be copied to the tester
  cd "$prefix_real"
  this="$name.build-${BUILD_NUMBER-$(date +%Y-%m-%d_%H_%M_%S)}"
  tar="${this}.tgz"
  tar czf "$base/$tar" *
  cd "$base"
  md5sum "$tar" > "${this}.md5"
}