package extensions

import (
	"testing"

	"{{ANIP_GO_MODULE_PATH}}/generated"
)

func TestSearchRefusesScopeQualifiersInQuery(t *testing.T) {
	for _, query := range []string{"repo:other/private", "bug REPO:other/private", "org:acme-private", "user: someone", "owner :someone"} {
		result, err := searchRepositoryContext(generated.GeneratedCapabilityRuntimeMetadata{CapabilityID: "github.repo.search_context"}, generated.BackendInvocationPlan{}, map[string]any{"owner": "acme", "repo": "demo", "query": query}, "token")
		if err != nil || result["execution_status"] != "restricted" || result["reason"] != scopeQualifierReason {
			t.Fatalf("%q: expected a restricted refusal, got %#v (%v)", query, result, err)
		}
	}
	for _, query := range []string{"label:bug repository crash", "is:issue myrepo"} {
		if scopeQualifier.MatchString(query) {
			t.Fatalf("%q: plain search terms must pass", query)
		}
	}
}

func TestSearchKeepsOnlyItemsFromTheRepository(t *testing.T) {
	if !itemInRepo(map[string]any{"repository_url": "https://api.github.com/repos/Acme/Demo"}, "acme", "demo") {
		t.Fatal("the requested repository's item was dropped")
	}
	for _, item := range []map[string]any{{"repository_url": "https://api.github.com/repos/other/private"}, {"repository_url": "https://api.github.com/repos/acme/demo-fork"}, {}} {
		if itemInRepo(item, "acme", "demo") {
			t.Fatalf("an item outside the repository was kept: %#v", item)
		}
	}
	if totalCount(map[string]any{"total_count": float64(3)}, 1) != nil {
		t.Fatal("total_count must not be reported once items were dropped")
	}
}
