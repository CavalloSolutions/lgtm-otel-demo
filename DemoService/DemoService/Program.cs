using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using System.Diagnostics.Metrics;
using OpenTelemetry.Logs;
using OpenTelemetry;
using System.Diagnostics;
using Microsoft.Data.SqlClient;
using Dapper;
using System.Text.Json;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddHttpClient();

var sqlConnStr = await InitDb(builder.Configuration);
var meter = InitOtel(builder.Configuration, builder.Services, builder.Logging);

var app = builder.Build();
app.UseSwagger();
app.UseSwaggerUI();

var arbitrary_counter = meter.CreateCounter<long>("arbitary_count_total");
var requestCounter = 0;

app.MapGet("/otel-demo", async () =>
{
    requestCounter++;
    arbitrary_counter.Add(Random.Shared.NextInt64(10));

    // periodically delay requests
    if (requestCounter % 1000 < 100)
    {
        app.Logger.LogWarning("Delaying request...");
        var ms = Random.Shared.Next(500, 1000);
        await Task.Delay(ms);
    }

    var httpClient = app.Services.GetRequiredService<HttpClient>();

    // demo auto-instrumented http client
    app.Logger.LogInformation("Making request to example.com...");
    httpClient.DefaultRequestHeaders.Add("test-header", new[] { "test-value" });
    await httpClient.GetAsync("http://example.com");

    // periodically throw an exception
    if (requestCounter % 1000 >= 475 && requestCounter % 1000 < 500)
    {
        throw new Exception("Periodic Exception!");
    }

    // demo nested spans/activities
    using (var activity = Activity.Current?.Source.StartActivity("Nested Activity"))
    {
        app.Logger.LogInformation("Doing work...");
        await Task.Delay(2);

        using (var subactivity = Activity.Current?.Source.StartActivity("Nested Nested Activity"))
        {
            app.Logger.LogInformation("Doing some more work...");
            await Task.Delay(4);
            app.Logger.LogInformation("Done...");
        }

        // demo auto-instrumented SQL client
        using (var sqlConn = new SqlConnection(sqlConnStr))
        {
            app.Logger.LogInformation("Querying sql-server...");
            var names = await sqlConn.QueryAsync<string>("Select Name from oteldemo");
            activity?.SetTag("Names", JsonSerializer.Serialize(names));
        }

        app.Logger.LogInformation("Done.");
    }
})
.WithName("OtelDemo");

app.Run();

public partial class Program
{
    public static async Task<string> InitDb(IConfiguration config)
    {
        var sqlConnStr = new SqlConnectionStringBuilder
        {
            DataSource = config["SQL_HOST"],
            UserID = config["SQL_USER"],
            Password = config["SQL_PASSWORD"],
            Encrypt = false
        };

        var dbname = "oteldemodb";

        using (var sqlConn = new SqlConnection(sqlConnStr.ToString()))
        {
            var sql = $@"
                IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = '{dbname}')
                BEGIN
                    CREATE DATABASE {dbname}
                END";

            await sqlConn.ExecuteAsync(sql);

            sql = $@"
                use {dbname};

                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='oteldemo' and xtype='U')
                BEGIN
                    
                    CREATE TABLE oteldemo (
                        Id INT PRIMARY KEY IDENTITY (1, 1),
                        Name NVARCHAR(MAX)
                    );

                    INSERT INTO oteldemo (Name) VALUES ('Bob'), ('Alice');
                END
                ";

            await sqlConn.ExecuteAsync(sql);
        }

        sqlConnStr.InitialCatalog = dbname;

        return sqlConnStr.ToString();
    }

    public static Meter InitOtel(IConfiguration config, IServiceCollection services, ILoggingBuilder logging)
    {
        var otlpEndpoint = new Uri(config["OTLP_URL"]);
        var serviceName = typeof(Program).Assembly.GetName().Name ?? "unknown";
        var serviceVersion = typeof(Program).Assembly.GetName().Version?.ToString() ?? "unknown";

        var meter = new Meter(serviceName, serviceVersion);

        void configureResource(ResourceBuilder r)
        {
            r.AddService(
                serviceName: serviceName,
                serviceNamespace: "demo",
                serviceVersion: serviceVersion,
                serviceInstanceId: Environment.MachineName);
        }

        var otelBuilder = services.AddOpenTelemetry()
            .ConfigureResource(configureResource);

        // Configure Tracing
        otelBuilder.WithTracing(builder => builder
            .AddAspNetCoreInstrumentation(configure =>
            {
                configure.EnrichWithHttpRequest = (activity, request) =>
                {

                };

                configure.EnrichWithHttpResponse = (activity, response) =>
                {

                };
            })
            .AddHttpClientInstrumentation(configure =>
            {
                configure.EnrichWithHttpRequestMessage = (activity, request) =>
                {
                    activity.SetTag("headers", JsonSerializer.Serialize(request.Headers));
                };
                configure.EnrichWithHttpResponseMessage = (activity, response) =>
                {

                };
            })
            .AddSqlClientInstrumentation(configure =>
            {
                configure.EnableConnectionLevelAttributes = true;
                configure.RecordException = true;
                configure.SetDbStatementForText = true;
                configure.Enrich = (activity, eventName, sqlCommand) =>
                {
                };
            })
            .AddOtlpExporter(configure => configure.Endpoint = otlpEndpoint));

        // Configure Metrics
        otelBuilder.WithMetrics(builder => builder
            .AddAspNetCoreInstrumentation(configure =>
            {
                configure.Enrich = (string name, HttpContext context, ref TagList tags) =>
                {

                };
            })
            .AddHttpClientInstrumentation()
            .AddOtlpExporter(configure => configure.Endpoint = otlpEndpoint)
            .AddMeter(meter.Name))
        .StartWithHost();

        // Configure Logging
        var rb = ResourceBuilder.CreateDefault();
        configureResource(rb);

        logging.AddOpenTelemetry(configure => configure
            .AddOtlpExporter(configure => configure.Endpoint = otlpEndpoint)
            .AddConsoleExporter()
            .SetResourceBuilder(rb));

        return meter;
    }
}