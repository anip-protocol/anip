package bundlerefs

import (
	"fmt"
	"net/url"
	"regexp"
	"strings"
	"unicode"
)

type CustomCodeBundleRef struct {
	Kind      string
	Locator   string
	Immutable string
	Digest    string
}

type CustomCodeBundleMaterial struct {
	Ref              string `json:"ref"`
	Kind             string `json:"kind,omitempty"`
	Locator          string `json:"locator,omitempty"`
	Immutable        string `json:"immutable,omitempty"`
	Digest           string `json:"digest,omitempty"`
	BundleTreeSHA256 string `json:"bundle_tree_sha256,omitempty"`
	Title            string `json:"title,omitempty"`
	Source           string `json:"source,omitempty"`
}

var (
	sha256DigestPattern        = regexp.MustCompile(`^[A-Fa-f0-9]{64}$`)
	gitCommitPattern           = regexp.MustCompile(`^[A-Fa-f0-9]{40,64}$`)
	registryBundleRefPattern   = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}@[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$`)
	objectStoreBucketPattern   = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9.-]{1,61}[A-Za-z0-9]$`)
	objectStoreKeySegment      = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._~+=,@-]*$`)
	customBundleRefBadChars    = regexp.MustCompile(`[<>\"'` + "`" + `{}|^\\]`)
	customBundleRefBranchNames = map[string]struct{}{
		"head":    {},
		"latest":  {},
		"main":    {},
		"master":  {},
		"stable":  {},
		"trunk":   {},
		"default": {},
	}
)

func ValidateCustomCodeBundleRef(raw string) (*CustomCodeBundleRef, error) {
	ref := strings.TrimSpace(raw)
	if ref == "" {
		return nil, fmt.Errorf("custom code bundle ref is required")
	}
	if len(ref) > 2048 {
		return nil, fmt.Errorf("custom code bundle ref is too long")
	}
	if containsControlOrSpace(ref) || customBundleRefBadChars.MatchString(ref) {
		return nil, fmt.Errorf("custom code bundle ref contains unsafe characters")
	}

	locator, digest, ok := strings.Cut(ref, "#sha256:")
	if !ok || locator == "" || digest == "" {
		return nil, fmt.Errorf("custom code bundle ref must include a sha256 digest fragment")
	}
	if strings.Contains(digest, "#") || !sha256DigestPattern.MatchString(digest) {
		return nil, fmt.Errorf("custom code bundle ref digest must be sha256:<64 hex chars>")
	}
	if strings.Contains(locator, "..") {
		return nil, fmt.Errorf("custom code bundle ref must not contain path traversal")
	}

	switch {
	case strings.HasPrefix(locator, "git+https://"):
		return validateGitCustomCodeBundleRef(locator, strings.ToLower(digest))
	case strings.HasPrefix(locator, "registry://"):
		return validateRegistryCustomCodeBundleRef(locator, strings.ToLower(digest))
	case strings.HasPrefix(locator, "object+https://"):
		return validateObjectHTTPSCustomCodeBundleRef(locator, strings.ToLower(digest))
	case strings.HasPrefix(locator, "object+s3://"):
		return validateObjectS3CustomCodeBundleRef(locator, strings.ToLower(digest))
	default:
		return nil, fmt.Errorf("custom code bundle ref scheme must be git+https, registry, object+https, or object+s3")
	}
}

func CustomCodeBundleMaterialsFromMetadata(manifest map[string]any, lock map[string]any) ([]CustomCodeBundleMaterial, error) {
	materials := []CustomCodeBundleMaterial{}
	if err := appendCustomCodeBundleMaterials(&materials, "manifest", manifest); err != nil {
		return nil, err
	}
	if err := appendCustomCodeBundleMaterials(&materials, "recommended_lock", lock); err != nil {
		return nil, err
	}
	return dedupeCustomCodeBundleMaterials(materials), nil
}

func appendCustomCodeBundleMaterials(materials *[]CustomCodeBundleMaterial, source string, metadata map[string]any) error {
	if len(metadata) == 0 {
		return nil
	}
	for _, key := range []string{"custom_code_bundle_ref", "custom_code_bundle_refs", "custom_code_bundles"} {
		if err := appendCustomCodeBundleMaterialValue(materials, source+"."+key, metadata[key]); err != nil {
			return err
		}
	}
	for _, key := range []string{"implementation_material", "implementation_materials", "implementation_material_refs"} {
		if err := appendCustomCodeBundleMaterialValue(materials, source+"."+key, metadata[key]); err != nil {
			return err
		}
	}
	return nil
}

func appendCustomCodeBundleMaterialValue(materials *[]CustomCodeBundleMaterial, source string, value any) error {
	switch typed := value.(type) {
	case nil:
		return nil
	case string:
		return appendCustomCodeBundleMaterialObject(materials, source, map[string]any{"ref": typed})
	case []any:
		for index, item := range typed {
			if err := appendCustomCodeBundleMaterialValue(materials, fmt.Sprintf("%s[%d]", source, index), item); err != nil {
				return err
			}
		}
	case []string:
		for index, item := range typed {
			if err := appendCustomCodeBundleMaterialObject(materials, fmt.Sprintf("%s[%d]", source, index), map[string]any{"ref": item}); err != nil {
				return err
			}
		}
	case map[string]any:
		if isCustomCodeBundleMaterialObject(typed) {
			return appendCustomCodeBundleMaterialObject(materials, source, typed)
		}
		for _, key := range []string{"custom_code_bundle_ref", "custom_code_bundle_refs", "custom_code_bundles"} {
			if err := appendCustomCodeBundleMaterialValue(materials, source+"."+key, typed[key]); err != nil {
				return err
			}
		}
	default:
		return fmt.Errorf("custom code bundle metadata at %s must be a string, object, or array", source)
	}
	return nil
}

func isCustomCodeBundleMaterialObject(value map[string]any) bool {
	for _, key := range []string{"ref", "uri", "url", "custom_code_bundle_ref", "bundle_tree_sha256", "tree_sha256", "local_tree_sha256"} {
		if strings.TrimSpace(stringValue(value[key])) != "" {
			return true
		}
	}
	return false
}

func appendCustomCodeBundleMaterialObject(materials *[]CustomCodeBundleMaterial, source string, value map[string]any) error {
	ref := firstNonEmpty(
		stringValue(value["ref"]),
		stringValue(value["uri"]),
		stringValue(value["url"]),
		stringValue(value["custom_code_bundle_ref"]),
	)
	if ref == "" {
		return nil
	}
	parsed, err := ValidateCustomCodeBundleRef(ref)
	if err != nil {
		return fmt.Errorf("invalid custom code bundle metadata at %s: %w", source, err)
	}
	treeDigest := firstNonEmpty(
		stringValue(value["bundle_tree_sha256"]),
		stringValue(value["tree_sha256"]),
		stringValue(value["local_tree_sha256"]),
	)
	if treeDigest != "" && !isSHA256DigestString(treeDigest) {
		return fmt.Errorf("invalid custom code bundle tree digest at %s: must be sha256:<64 hex chars>", source)
	}
	*materials = append(*materials, CustomCodeBundleMaterial{
		Ref:              ref,
		Kind:             parsed.Kind,
		Locator:          parsed.Locator,
		Immutable:        parsed.Immutable,
		Digest:           parsed.Digest,
		BundleTreeSHA256: strings.ToLower(treeDigest),
		Title:            stringValue(value["title"]),
		Source:           source,
	})
	return nil
}

func dedupeCustomCodeBundleMaterials(materials []CustomCodeBundleMaterial) []CustomCodeBundleMaterial {
	result := []CustomCodeBundleMaterial{}
	seen := map[string]struct{}{}
	for _, material := range materials {
		key := material.Ref + "\x00" + material.BundleTreeSHA256
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		result = append(result, material)
	}
	return result
}

func IsSHA256Digest(value string) bool {
	return isSHA256DigestString(value)
}

func isSHA256DigestString(value string) bool {
	trimmed := strings.ToLower(strings.TrimSpace(value))
	if !strings.HasPrefix(trimmed, "sha256:") {
		return false
	}
	digest := strings.TrimPrefix(trimmed, "sha256:")
	return sha256DigestPattern.MatchString(digest)
}

func validateGitCustomCodeBundleRef(locator string, digest string) (*CustomCodeBundleRef, error) {
	at := strings.LastIndex(locator, "@")
	if at < len("git+https://")+1 || at == len(locator)-1 {
		return nil, fmt.Errorf("git custom code bundle ref must pin a commit with @<commit>")
	}
	repoLocator := locator[:at]
	commit := locator[at+1:]
	if !gitCommitPattern.MatchString(commit) {
		return nil, fmt.Errorf("git custom code bundle ref must pin an immutable commit hash")
	}
	parsed, err := url.Parse("https://" + strings.TrimPrefix(repoLocator, "git+https://"))
	if err != nil || parsed.Scheme != "https" || parsed.Host == "" || parsed.Path == "" {
		return nil, fmt.Errorf("git custom code bundle ref must be a valid HTTPS git URL")
	}
	if parsed.User != nil || parsed.RawQuery != "" || parsed.Fragment != "" {
		return nil, fmt.Errorf("git custom code bundle ref must not include credentials, query, or fragment before the digest")
	}
	if !safeURLPath(parsed.Path) {
		return nil, fmt.Errorf("git custom code bundle ref path is unsafe")
	}
	return &CustomCodeBundleRef{Kind: "git", Locator: repoLocator, Immutable: commit, Digest: "sha256:" + digest}, nil
}

func validateRegistryCustomCodeBundleRef(locator string, digest string) (*CustomCodeBundleRef, error) {
	value := strings.TrimPrefix(locator, "registry://")
	if value == "" || strings.Contains(value, "//") || strings.Contains(value, "\\") || strings.Contains(value, "?") {
		return nil, fmt.Errorf("registry custom code bundle ref is invalid")
	}
	at := strings.LastIndex(value, "@")
	if at <= 0 || at == len(value)-1 {
		return nil, fmt.Errorf("registry custom code bundle ref must include @<version>")
	}
	version := strings.ToLower(value[at+1:])
	if _, floating := customBundleRefBranchNames[version]; floating {
		return nil, fmt.Errorf("registry custom code bundle ref must pin an immutable version")
	}
	if !registryBundleRefPattern.MatchString(value) {
		return nil, fmt.Errorf("registry custom code bundle ref is invalid")
	}
	return &CustomCodeBundleRef{Kind: "registry", Locator: "registry://" + value[:at], Immutable: value[at+1:], Digest: "sha256:" + digest}, nil
}

func validateObjectHTTPSCustomCodeBundleRef(locator string, digest string) (*CustomCodeBundleRef, error) {
	parsed, err := url.Parse("https://" + strings.TrimPrefix(locator, "object+https://"))
	if err != nil || parsed.Scheme != "https" || parsed.Host == "" || parsed.Path == "" || parsed.Path == "/" {
		return nil, fmt.Errorf("object HTTPS custom code bundle ref must be a valid HTTPS object URL")
	}
	if parsed.User != nil || parsed.RawQuery != "" || parsed.Fragment != "" {
		return nil, fmt.Errorf("object HTTPS custom code bundle ref must not include credentials, query, or fragment before the digest")
	}
	if !safeURLPath(parsed.Path) {
		return nil, fmt.Errorf("object HTTPS custom code bundle ref path is unsafe")
	}
	return &CustomCodeBundleRef{Kind: "object+https", Locator: locator, Digest: "sha256:" + digest}, nil
}

func validateObjectS3CustomCodeBundleRef(locator string, digest string) (*CustomCodeBundleRef, error) {
	parsed, err := url.Parse(strings.TrimPrefix(locator, "object+"))
	if err != nil || parsed.Scheme != "s3" || parsed.Host == "" || parsed.Path == "" || parsed.Path == "/" {
		return nil, fmt.Errorf("object S3 custom code bundle ref must be a valid s3 object URL")
	}
	if parsed.User != nil || parsed.RawQuery != "" || parsed.Fragment != "" {
		return nil, fmt.Errorf("object S3 custom code bundle ref must not include credentials, query, or fragment before the digest")
	}
	if !objectStoreBucketPattern.MatchString(parsed.Host) || !safeURLPath(parsed.Path) {
		return nil, fmt.Errorf("object S3 custom code bundle ref path is unsafe")
	}
	return &CustomCodeBundleRef{Kind: "object+s3", Locator: locator, Digest: "sha256:" + digest}, nil
}

func containsControlOrSpace(value string) bool {
	for _, r := range value {
		if unicode.IsControl(r) || unicode.IsSpace(r) {
			return true
		}
	}
	return false
}

func safeURLPath(path string) bool {
	if path == "" || strings.Contains(path, "\\") || strings.Contains(path, "//") {
		return false
	}
	for _, segment := range strings.Split(strings.Trim(path, "/"), "/") {
		if segment == "" || segment == "." || segment == ".." || !objectStoreKeySegment.MatchString(segment) {
			return false
		}
	}
	return true
}

func stringValue(value any) string {
	text, _ := value.(string)
	return text
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}
