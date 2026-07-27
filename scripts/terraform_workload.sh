#!/usr/bin/env bash
set -euo pipefail

umask 077

if [[ -z "${HOME:-}" ]]; then
  echo "HOME vazio; abortando." >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
STACK_DIR="${REPO_ROOT}/infrastructure/terraform"

WORKLOAD_STATE_DIR="${WORKLOAD_STATE_DIR:-${HOME}/.local/state/edudocs/workload}"
WORKLOAD_STATE_PATH="${WORKLOAD_STATE_PATH:-${WORKLOAD_STATE_DIR}/terraform.tfstate}"
WORKLOAD_TF_DATA_DIR="${WORKLOAD_TF_DATA_DIR:-${HOME}/.local/share/edudocs/terraform-workload}"

resolve_existing_or_parent() {
  local path="$1"
  if [[ -e "$path" ]]; then
    cd -- "$path" 2>/dev/null && pwd -P && return 0
    local dir
    dir="$(cd -- "$(dirname -- "$path")" && pwd -P)"
    printf '%s/%s\n' "$dir" "$(basename -- "$path")"
    return 0
  fi
  local parent
  parent="$(cd -- "$(dirname -- "$path")" && pwd -P)"
  printf '%s/%s\n' "$parent" "$(basename -- "$path")"
}

ensure_outside_repo() {
  local label="$1"
  local path="$2"
  local resolved
  resolved="$(resolve_existing_or_parent "$path")"
  case "$resolved" in
    "$REPO_ROOT"|"$REPO_ROOT"/*)
      echo "${label} dentro do repositorio; abortando." >&2
      exit 2
      ;;
  esac
}

reject_extra_args() {
  if [[ "$#" -ne 0 ]]; then
    echo "Argumentos extras nao permitidos." >&2
    exit 2
  fi
}

reject_option_like_path() {
  local value="$1"
  case "$value" in
    -*|*"-target"*|*"refresh=false"*|*"-auto-approve"*)
      echo "Opcao proibida em argumento de caminho." >&2
      exit 2
      ;;
  esac
}

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "Arquivo obrigatorio ausente." >&2
    exit 2
  fi
}

repo_file() {
  local path="$1"
  if [[ "$path" = /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s/%s\n' "$REPO_ROOT" "$path"
  fi
}

require_tmp_plan() {
  local path="$1"
  reject_option_like_path "$path"
  require_file "$path"
  if [[ -d "$path" ]]; then
    echo "Planfile nao pode ser diretorio." >&2
    exit 2
  fi
  case "$path" in
    /tmp/*.tfplan) ;;
    *)
      echo "Planfile precisa estar em /tmp e terminar em .tfplan." >&2
      exit 2
      ;;
  esac
  local mode
  mode="$(stat -c '%a' "$path")"
  if [[ "$mode" != "600" ]]; then
    echo "Planfile precisa ter permissao 600." >&2
    exit 2
  fi
}

mkdir -p -- "$WORKLOAD_STATE_DIR" "$WORKLOAD_TF_DATA_DIR"
chmod 700 "$WORKLOAD_STATE_DIR" "$WORKLOAD_TF_DATA_DIR"
ensure_outside_repo "WORKLOAD_STATE_DIR" "$WORKLOAD_STATE_DIR"
ensure_outside_repo "WORKLOAD_STATE_PATH" "$WORKLOAD_STATE_PATH"
ensure_outside_repo "WORKLOAD_TF_DATA_DIR" "$WORKLOAD_TF_DATA_DIR"

export TF_DATA_DIR="$WORKLOAD_TF_DATA_DIR"

command="${1:-}"
if [[ -z "$command" ]]; then
  echo "Comando obrigatorio." >&2
  exit 2
fi
shift

case "$command" in
  init)
    reject_extra_args "$@"
    terraform -chdir="$STACK_DIR" init \
      -reconfigure \
      -input=false \
      -backend-config="path=$WORKLOAD_STATE_PATH"
    ;;
  validate)
    reject_extra_args "$@"
    terraform -chdir="$STACK_DIR" validate
    ;;
  state-list)
    reject_extra_args "$@"
    if [[ ! -f "$WORKLOAD_STATE_PATH" ]]; then
      exit 0
    fi
    terraform -chdir="$STACK_DIR" state list
    ;;
  plan)
    if [[ "$#" -ne 2 ]]; then
      echo "Uso: plan PLANFILE VARFILE." >&2
      exit 2
    fi
    planfile="$1"
    varfile="$2"
    reject_option_like_path "$planfile"
    reject_option_like_path "$varfile"
    varfile_path="$(repo_file "$varfile")"
    require_file "$varfile_path"
    if [[ -d "$planfile" ]]; then
      echo "Planfile nao pode ser diretorio." >&2
      exit 2
    fi
    terraform -chdir="$STACK_DIR" plan \
      -input=false \
      -var-file="$varfile_path" \
      -out="$planfile"
    chmod 600 "$planfile"
    ;;
  show-json)
    if [[ "$#" -ne 1 ]]; then
      echo "Uso: show-json PLANFILE." >&2
      exit 2
    fi
    reject_option_like_path "$1"
    require_file "$1"
    terraform -chdir="$STACK_DIR" show -json "$1"
    ;;
  show-text)
    if [[ "$#" -ne 1 ]]; then
      echo "Uso: show-text PLANFILE." >&2
      exit 2
    fi
    reject_option_like_path "$1"
    require_file "$1"
    terraform -chdir="$STACK_DIR" show "$1"
    ;;
  apply-saved-plan)
    if [[ "$#" -ne 1 ]]; then
      echo "Uso: apply-saved-plan PLANFILE." >&2
      exit 2
    fi
    require_tmp_plan "$1"
    terraform -chdir="$STACK_DIR" apply -input=false "$1"
    ;;
  output-json)
    reject_extra_args "$@"
    terraform -chdir="$STACK_DIR" output -json
    ;;
  post-apply-plan)
    if [[ "$#" -ne 2 ]]; then
      echo "Uso: post-apply-plan PLANFILE VARFILE." >&2
      exit 2
    fi
    planfile="$1"
    varfile="$2"
    reject_option_like_path "$planfile"
    reject_option_like_path "$varfile"
    varfile_path="$(repo_file "$varfile")"
    require_file "$varfile_path"
    terraform -chdir="$STACK_DIR" plan \
      -detailed-exitcode \
      -input=false \
      -var-file="$varfile_path" \
      -out="$planfile"
    chmod 600 "$planfile"
    ;;
  *)
    echo "Comando desconhecido: $command" >&2
    exit 2
    ;;
esac
