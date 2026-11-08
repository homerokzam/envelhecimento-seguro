var builder = WebApplication.CreateBuilder(args);
var origin = builder.Configuration["Analytics:BaseUrl"] ?? "http://127.0.0.1:8091";
if (!Uri.TryCreate(origin, UriKind.Absolute, out var baseUri) ||
    (baseUri.Scheme != "http" && baseUri.Scheme != "https"))
    throw new InvalidOperationException("Analytics:BaseUrl deve ser um endereço HTTP(S).");

builder.Services.AddHttpClient("analytics", client =>
{
    client.BaseAddress = baseUri;
    client.Timeout = TimeSpan.FromSeconds(15);
}).ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler { AllowAutoRedirect = false });

var app = builder.Build();
app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

app.MapGet("/api/dashboard", (HttpContext context, IHttpClientFactory clients) =>
    Forward(context, clients, "/dashboard"));
app.MapGet("/api/export.csv", (HttpContext context, IHttpClientFactory clients) =>
    Forward(context, clients, "/export.csv"));
app.MapGet("/api/dataset/status", (HttpContext context, IHttpClientFactory clients) =>
    Forward(context, clients, "/dataset/status"));
app.MapPost("/api/dataset/update", (HttpContext context, IHttpClientFactory clients) =>
    Forward(context, clients, "/dataset/update", HttpMethod.Post));

app.Run();

static async Task<IResult> Forward(HttpContext context, IHttpClientFactory clients, string path,
    HttpMethod? method = null)
{
    try
    {
        using var client = clients.CreateClient("analytics");
        using var request = new HttpRequestMessage(method ?? HttpMethod.Get, path + context.Request.QueryString);
        if (request.Method == HttpMethod.Post)
            request.Content = new StreamContent(context.Request.Body);
        using var response = await client.SendAsync(request, context.RequestAborted);
        var status = (int)response.StatusCode;
        if (status is not (200 or 202 or 400 or 409))
            return Results.Problem("O serviço de análise não conseguiu responder.", statusCode: 502);

        var bytes = await response.Content.ReadAsByteArrayAsync(context.RequestAborted);
        if (path == "/export.csv" && status == 200)
            return Results.File(bytes, "text/csv; charset=utf-8", "internacoes-por-quedas.csv");

        context.Response.StatusCode = status;
        return Results.Bytes(bytes, "application/json; charset=utf-8");
    }
    catch (OperationCanceledException) when (!context.RequestAborted.IsCancellationRequested)
    {
        return Results.Problem("O serviço de análise demorou para responder.", statusCode: 504);
    }
    catch (HttpRequestException)
    {
        return Results.Problem("O serviço de análise está indisponível.", statusCode: 503);
    }
}
