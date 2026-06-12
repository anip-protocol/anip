FROM mcr.microsoft.com/dotnet/sdk:10.0

WORKDIR /repo

COPY packages/csharp /repo/packages/csharp
COPY examples/showcase/gtm/generated/language-parity/csharp /repo/examples/showcase/gtm/generated/language-parity/csharp

WORKDIR /repo/examples/showcase/gtm/generated/language-parity/csharp

RUN dotnet test --nologo && dotnet publish -c Release -o /app --nologo

WORKDIR /app

EXPOSE 4100

CMD ["dotnet", "GTMPipelineQ2Review.dll"]
