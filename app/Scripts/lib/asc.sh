# Sourced by archive.sh and upload.sh: the App Store Connect API key, from the environment.
#
#   ASC_KEY_ID      the key's ID (10 characters)
#   ASC_ISSUER_ID   the issuer ID (a UUID)
#   ASC_KEY_PATH    the .p8 file (default ~/.appstoreconnect/private_keys/AuthKey_${ASC_KEY_ID}.p8)
#
# When ASC_KEY_ID or ASC_ISSUER_ID is unset and ASC_ENV (default ~/.cache/polished/asc.env, outside
# the repository) exists, it is read first. Nothing here prints or stores the values.

load_asc() {
  asc_env="${ASC_ENV:-$HOME/.cache/polished/asc.env}"
  if [ -z "${ASC_KEY_ID:-}" ] || [ -z "${ASC_ISSUER_ID:-}" ]; then
    if [ -f "$asc_env" ]; then
      set -a
      # shellcheck disable=SC1090
      . "$asc_env"
      set +a
    fi
  fi
  [ -n "${ASC_KEY_ID:-}" ] || { echo "ASC_KEY_ID is not set (the key's ID; docs/NATIVE.md section 7)" >&2; return 1; }
  [ -n "${ASC_ISSUER_ID:-}" ] || { echo "ASC_ISSUER_ID is not set (the issuer ID; docs/NATIVE.md section 7)" >&2; return 1; }
  ASC_KEY_PATH="${ASC_KEY_PATH:-$HOME/.appstoreconnect/private_keys/AuthKey_${ASC_KEY_ID}.p8}"
  [ -f "$ASC_KEY_PATH" ] || { echo "the API key file is missing: $ASC_KEY_PATH (set ASC_KEY_PATH, or put AuthKey_<ASC_KEY_ID>.p8 in ~/.appstoreconnect/private_keys)" >&2; return 1; }
  return 0
}
