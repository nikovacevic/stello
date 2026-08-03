#!/bin/sh
# stello installer — downloads the standalone binary for this platform, verifies it, and
# puts it on your PATH. No Python, uv, or git required to install.
#
#   curl -LsSf https://raw.githubusercontent.com/nikovacevic/stello/main/install.sh | sh
#
# Options (env vars, or flags after `-s --`):
#   STELLO_VERSION=0.1.0   install a specific version instead of the latest release
#   STELLO_HOME=~/.stello  install root (binary goes in $STELLO_HOME/bin)
#   --version X.Y.Z        same as STELLO_VERSION
#   --no-modify-path       don't touch shell profiles

set -eu

REPO="nikovacevic/stello"
BIN_NAME="stello"

VERSION="${STELLO_VERSION:-}"
MODIFY_PATH=1

info() { printf '%s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
err() {
	printf 'error: %s\n' "$*" >&2
	exit 1
}

while [ $# -gt 0 ]; do
	case "$1" in
	--version)
		VERSION="${2:-}"
		shift 2
		;;
	--no-modify-path)
		MODIFY_PATH=0
		shift
		;;
	*) err "unknown option: $1" ;;
	esac
done

# --- detect the target -----------------------------------------------------------------
detect_asset() {
	os="$(uname -s)"
	arch="$(uname -m)"
	case "$os" in
	Darwin)
		case "$arch" in
		arm64 | aarch64) echo "stello-macos-arm64" ;;
		x86_64) echo "stello-macos-x86_64" ;;
		*) err "unsupported macOS architecture: $arch" ;;
		esac
		;;
	Linux)
		case "$arch" in
		x86_64 | amd64) echo "stello-linux-x86_64" ;;
		*) err "unsupported Linux architecture: $arch (only x86_64 is published today)" ;;
		esac
		;;
	*) err "unsupported operating system: $os" ;;
	esac
}

# --- helpers ---------------------------------------------------------------------------
have() { command -v "$1" >/dev/null 2>&1; }

download() { # url dest
	if have curl; then
		curl -fsSL "$1" -o "$2"
	elif have wget; then
		wget -qO "$2" "$1"
	else
		err "need curl or wget to download"
	fi
}

sha256_of() { # file
	if have sha256sum; then
		sha256sum "$1" | awk '{print $1}'
	elif have shasum; then
		shasum -a 256 "$1" | awk '{print $1}'
	else
		err "need sha256sum or shasum to verify the download"
	fi
}

# --- resolve URLs ----------------------------------------------------------------------
ASSET="$(detect_asset)"
if [ -n "$VERSION" ]; then
	base="https://github.com/$REPO/releases/download/v${VERSION#v}"
else
	base="https://github.com/$REPO/releases/latest/download"
fi

# --- download + verify -----------------------------------------------------------------
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM

info "Downloading $ASSET (${VERSION:-latest})..."
download "$base/$ASSET" "$tmp/$ASSET"
download "$base/SHA256SUMS" "$tmp/SHA256SUMS"

expected="$(awk -v a="$ASSET" '$2 == a {print $1}' "$tmp/SHA256SUMS")"
[ -n "$expected" ] || err "no checksum for $ASSET in SHA256SUMS"
actual="$(sha256_of "$tmp/$ASSET")"
[ "$expected" = "$actual" ] || err "checksum mismatch for $ASSET (expected $expected, got $actual)"

# --- install ---------------------------------------------------------------------------
home="${STELLO_HOME:-$HOME/.stello}"
bin_dir="$home/bin"
mkdir -p "$bin_dir"
install -m 0755 "$tmp/$ASSET" "$bin_dir/$BIN_NAME" 2>/dev/null ||
	{ cp "$tmp/$ASSET" "$bin_dir/$BIN_NAME" && chmod 0755 "$bin_dir/$BIN_NAME"; }
info "Installed $BIN_NAME to $bin_dir/$BIN_NAME"

# --- PATH --------------------------------------------------------------------------------
on_path=0
case ":$PATH:" in *":$bin_dir:"*) on_path=1 ;; esac

if [ "$on_path" -eq 0 ] && [ "$MODIFY_PATH" -eq 1 ]; then
	# Write $HOME-relative when possible, so the line is portable across machines.
	case "$bin_dir" in
	"$HOME"/*) path_expr="\$HOME${bin_dir#"$HOME"}" ;;
	*) path_expr="$bin_dir" ;;
	esac
	case "${SHELL:-}" in
	*/zsh) profile="$HOME/.zshrc" ;;
	*/bash) profile="$HOME/.bashrc" ;;
	*) profile="" ;;
	esac
	if [ -n "$profile" ]; then
		if ! { [ -f "$profile" ] && grep -qF "$bin_dir" "$profile"; }; then
			printf '\n# stello\nexport PATH="%s:$PATH"\n' "$path_expr" >>"$profile"
			info "Added $bin_dir to PATH in $profile — restart your shell or run: export PATH=\"$bin_dir:\$PATH\""
		fi
	else
		info "Add $bin_dir to your PATH:  export PATH=\"$bin_dir:\$PATH\""
	fi
elif [ "$on_path" -eq 0 ]; then
	info "Add $bin_dir to your PATH:  export PATH=\"$bin_dir:\$PATH\""
fi

# --- runtime tools -----------------------------------------------------------------------
# stello installs without git/uv, but needs them to *operate*: git to fetch projects, uv to
# run Python apps. Flag anything missing so the first `stello install`/`run` isn't a surprise.
missing=""
have git || missing="git"
have uv || missing="${missing:+$missing and }uv"
if [ -n "$missing" ]; then
	info ""
	warn "stello uses $missing at runtime, but it isn't on your PATH."
	info "  git: https://git-scm.com/downloads"
	info "  uv:  https://docs.astral.sh/uv/getting-started/installation/"
fi

info ""
info "Done. Run '$BIN_NAME --help' to get started."
