# docker-bake-latest.hcl — Adds :latest tags when on main branch

variable "REGISTRY" {
  default = "ghcr.io"
}

variable "IMAGE_NAME_LOWER" {
  default = "refractsystems/virtmcu"
}

variable "IMAGE_TAG" {
  default = "latest"
}

variable "ARCH" {
  default = "amd64"
}

target "base" {
  tags = [
    "${REGISTRY}/${IMAGE_NAME_LOWER}/base:latest-${ARCH}",
    "${REGISTRY}/${IMAGE_NAME_LOWER}/base:${IMAGE_TAG}-${ARCH}"
  ]
}

target "toolchain" {
  tags = [
    "${REGISTRY}/${IMAGE_NAME_LOWER}/toolchain:latest-${ARCH}",
    "${REGISTRY}/${IMAGE_NAME_LOWER}/toolchain:${IMAGE_TAG}-${ARCH}"
  ]
}

target "devenv-base" {
  tags = [
    "${REGISTRY}/${IMAGE_NAME_LOWER}/devenv-base:latest-${ARCH}",
    "${REGISTRY}/${IMAGE_NAME_LOWER}/devenv-base:${IMAGE_TAG}-${ARCH}"
  ]
}

target "builder" {
  tags = [
    "${REGISTRY}/${IMAGE_NAME_LOWER}/builder:latest-${ARCH}",
    "${REGISTRY}/${IMAGE_NAME_LOWER}/builder:${IMAGE_TAG}-${ARCH}"
  ]
}

target "devenv" {
  tags = [
    "${REGISTRY}/${IMAGE_NAME_LOWER}/devenv:latest-${ARCH}",
    "${REGISTRY}/${IMAGE_NAME_LOWER}/devenv:${IMAGE_TAG}-${ARCH}"
  ]
}

target "runtime" {
  tags = [
    "${REGISTRY}/${IMAGE_NAME_LOWER}/runtime:latest-${ARCH}",
    "${REGISTRY}/${IMAGE_NAME_LOWER}/runtime:${IMAGE_TAG}-${ARCH}"
  ]
}
