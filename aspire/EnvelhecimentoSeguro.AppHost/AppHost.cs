using Aspire.Hosting;

var builder = DistributedApplication.CreateBuilder(args);

// Prefere o .venv do serviço (tem PySUS e pandas); senão usa o python3.14 do PATH.
var venvPython = Path.GetFullPath(Path.Combine(builder.AppHostDirectory,
    "../../backend/webapi-python/.venv/bin/python"));
var python = builder.AddExecutable("analytics",
        builder.Configuration["PYTHON_EXECUTABLE"] ?? (File.Exists(venvPython) ? venvPython : "python3.14"),
        "../../backend/webapi-python",
        "-m", "analytics.server")
    .WithHttpEndpoint(env: "PORT")
    .WithEnvironment("DATA_DIR", builder.Configuration["DATA_DIR"] ?? "")
    .WithEnvironment("POPULATION_CSV", builder.Configuration["POPULATION_CSV"] ?? "")
    .WithEnvironment("PYTHONUNBUFFERED", "1")
    .WithHttpHealthCheck("/health");

var api = builder.AddProject<Projects.EnvelhecimentoSeguro_WebApi>("webapi", launchProfileName: null)
    .WithHttpEndpoint(env: "ASPNETCORE_HTTP_PORTS")
    .WithEnvironment("Analytics__BaseUrl", python.GetEndpoint("http"))
    .WithHttpHealthCheck("/health")
    .WaitFor(python);

builder.AddExecutable("webapp", "npm", "../../frontend/webapp", "run", "dev")
    .WithHttpEndpoint(env: "PORT")
    .WithEnvironment("API_PROXY_TARGET", api.GetEndpoint("http"))
    .WithExternalHttpEndpoints()
    .WaitFor(api);

builder.Build().Run();
