package generator

import "github.com/anip-protocol/anip/packages/go/bundlerefs"

type CustomCodeBundleRef = bundlerefs.CustomCodeBundleRef
type CustomCodeBundleMaterial = bundlerefs.CustomCodeBundleMaterial

func ValidateCustomCodeBundleRef(raw string) (*CustomCodeBundleRef, error) {
	return bundlerefs.ValidateCustomCodeBundleRef(raw)
}

func CustomCodeBundleMaterialsFromMetadata(manifest map[string]any, lock map[string]any) ([]CustomCodeBundleMaterial, error) {
	return bundlerefs.CustomCodeBundleMaterialsFromMetadata(manifest, lock)
}

func IsSHA256Digest(value string) bool {
	return bundlerefs.IsSHA256Digest(value)
}
