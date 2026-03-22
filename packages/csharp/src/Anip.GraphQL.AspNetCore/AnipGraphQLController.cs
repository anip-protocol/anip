using System.Text.Json;
using Anip.GraphQL;
using Anip.Service;
using GraphQL;
using GraphQL.Types;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;

namespace Anip.GraphQL.AspNetCore;

/// <summary>
/// ASP.NET Core controller for ANIP GraphQL interface.
/// POST /graphql: execute query/mutation
/// GET /graphql: playground HTML (Accept: text/html)
/// GET /schema.graphql: SDL text
/// </summary>
[ApiController]
public class AnipGraphQLController : ControllerBase
{
    private readonly ISchema _schema;
    private readonly string _sdlText;
    private readonly IDocumentExecuter _executer;

    public AnipGraphQLController(AnipService service)
    {
        var schemaResult = SchemaBuilder.BuildSchema(service);
        _schema = schemaResult.Schema;
        _sdlText = schemaResult.Sdl;
        _executer = new DocumentExecuter();
    }

    [HttpPost("/graphql")]
    [Produces("application/json")]
    public async Task<IActionResult> ExecuteGraphQL()
    {
        Dictionary<string, JsonElement>? body;
        try
        {
            body = await JsonSerializer.DeserializeAsync<Dictionary<string, JsonElement>>(Request.Body);
        }
        catch
        {
            return Ok(new Dictionary<string, object?>
            {
                ["errors"] = new List<object> { new Dictionary<string, object?> { ["message"] = "Invalid request body" } },
            });
        }

        if (body == null)
        {
            return Ok(new Dictionary<string, object?>
            {
                ["errors"] = new List<object> { new Dictionary<string, object?> { ["message"] = "Missing request body" } },
            });
        }

        string? query = null;
        Dictionary<string, object?>? variables = null;
        string? operationName = null;

        if (body.TryGetValue("query", out var queryEl))
        {
            query = queryEl.GetString();
        }
        if (body.TryGetValue("variables", out var varsEl) && varsEl.ValueKind == JsonValueKind.Object)
        {
            variables = JsonSerializer.Deserialize<Dictionary<string, object?>>(varsEl.GetRawText());
        }
        if (body.TryGetValue("operationName", out var opEl))
        {
            operationName = opEl.GetString();
        }

        if (string.IsNullOrEmpty(query))
        {
            return Ok(new Dictionary<string, object?>
            {
                ["errors"] = new List<object> { new Dictionary<string, object?> { ["message"] = "Missing query" } },
            });
        }

        // Inject auth header into user context so resolvers can access it.
        var authHeader = Request.Headers.Authorization.FirstOrDefault() ?? "";
        var userContext = new Dictionary<string, object?>
        {
            ["authHeader"] = authHeader,
        };

        var execResult = await _executer.ExecuteAsync(options =>
        {
            options.Schema = _schema;
            options.Query = query;
            options.Variables = variables != null ? new Inputs(variables) : null;
            options.OperationName = operationName;
            options.UserContext = userContext;
        });

        var response = new Dictionary<string, object?>();
        if (execResult.Data != null)
        {
            response["data"] = execResult.Data;
        }
        if (execResult.Errors != null && execResult.Errors.Count > 0)
        {
            response["errors"] = execResult.Errors.Select(e =>
                new Dictionary<string, object?> { ["message"] = e.Message }).ToList();
        }

        // Always return 200 for GraphQL (errors in body, not HTTP status).
        return Ok(response);
    }

    [HttpGet("/graphql")]
    [Produces("text/html")]
    public ContentResult Playground()
    {
        var html = """
                   <!DOCTYPE html>
                   <html><head><title>ANIP GraphQL</title></head><body>
                   <h2>ANIP GraphQL Playground</h2>
                   <textarea id="q" rows="10" cols="60">{ }</textarea><br>
                   <button onclick="run()">Run</button><pre id="r"></pre>
                   <script>
                   async function run() {
                     const r = await fetch("/graphql", {
                       method: "POST",
                       headers: {"Content-Type": "application/json"},
                       body: JSON.stringify({query: document.getElementById("q").value})
                     });
                     document.getElementById("r").textContent = JSON.stringify(await r.json(), null, 2);
                   }
                   </script></body></html>
                   """;
        return Content(html, "text/html");
    }

    [HttpGet("/schema.graphql")]
    [Produces("text/plain")]
    public ContentResult Schema()
    {
        return Content(_sdlText, "text/plain");
    }
}
