package {{ANIP_JAVA_PACKAGE_NAME}};

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class GitHubSearchScopeTest {

    @Test
    void queriesCarryingScopeQualifiersAreRefused() {
        for (String query : List.of("repo:other/private", "bug REPO:other/private", "org:acme-private", "user: someone", "owner :someone")) {
            assertTrue(GitHubBackendAdapter.SCOPE_QUALIFIER.matcher(query).find(), query);
        }
        assertFalse(GitHubBackendAdapter.SCOPE_QUALIFIER.matcher("label:bug repository crash").find());
    }

    @Test
    void onlyItemsFromTheRepositoryAreKept() {
        assertTrue(GitHubBackendAdapter.itemInRepo(Map.of("repository_url", "https://api.github.com/repos/Acme/Demo"), "acme", "demo"));
        assertFalse(GitHubBackendAdapter.itemInRepo(Map.of("repository_url", "https://api.github.com/repos/other/private"), "acme", "demo"));
        assertFalse(GitHubBackendAdapter.itemInRepo(Map.of("repository_url", "https://api.github.com/repos/acme/demo-fork"), "acme", "demo"));
        assertFalse(GitHubBackendAdapter.itemInRepo(Map.of(), "acme", "demo"));
    }
}
