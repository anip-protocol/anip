using System.Text.Json;
using Xunit;
using {{ANIP_CSHARP_ROOT_NAMESPACE}};

namespace {{ANIP_CSHARP_ROOT_NAMESPACE}}.Tests;

public class GitHubSearchScopeTests
{
    [Theory]
    [InlineData("repo:other/private")]
    [InlineData("bug REPO:other/private")]
    [InlineData("org:acme-private")]
    [InlineData("user: someone")]
    [InlineData("owner :someone")]
    public void QueriesCarryingScopeQualifiersAreRefused(string query)
    {
        var previous = Environment.GetEnvironmentVariable("GITHUB_TOKEN");
        Environment.SetEnvironmentVariable("GITHUB_TOKEN", "token");
        try
        {
            var parameters = new Dictionary<string, object?> { ["owner"] = "acme", ["repo"] = "demo", ["query"] = query };
            var result = BackendAdapter.Default(new Dictionary<string, object?> { ["capability_id"] = "github.repo.search_context" }, Plan(parameters), parameters, null!);
            Assert.Equal("restricted", result["execution_status"]);
        }
        finally
        {
            Environment.SetEnvironmentVariable("GITHUB_TOKEN", previous);
        }
    }

    [Fact]
    public void PlainSearchTermsPass() => Assert.False(BackendAdapter.ScopeQualifier.IsMatch("label:bug repository crash"));

    [Fact]
    public void OnlyItemsFromTheRepositoryAreKept()
    {
        Assert.True(BackendAdapter.ItemInRepo(Item("""{"repository_url":"https://api.github.com/repos/Acme/Demo"}"""), "acme", "demo"));
        Assert.False(BackendAdapter.ItemInRepo(Item("""{"repository_url":"https://api.github.com/repos/other/private"}"""), "acme", "demo"));
        Assert.False(BackendAdapter.ItemInRepo(Item("""{"repository_url":"https://api.github.com/repos/acme/demo-fork"}"""), "acme", "demo"));
        Assert.False(BackendAdapter.ItemInRepo(Item("{}"), "acme", "demo"));
    }

    private static JsonElement Item(string json) => JsonDocument.Parse(json).RootElement;

    private static Dictionary<string, object?> Plan(Dictionary<string, object?> parameters) => new()
    {
        ["selected_binding"] = null,
        ["semantic_input"] = parameters,
        ["adapter_input"] = parameters,
        ["backend_input_contract"] = new Dictionary<string, object?> { ["mode"] = "explicit", ["required"] = Array.Empty<string>(), ["optional"] = Array.Empty<string>() },
        ["unresolved_required_backend_inputs"] = Array.Empty<string>(),
    };
}
