# HL7UnitTests test image (no HTML/TRX report generation)
# syntax=docker/dockerfile:1.7

FROM mcr.microsoft.com/dotnet/sdk:8.0

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Optional NuGet config can be injected securely via BuildKit secret `nuget_config`.
RUN mkdir -p /root/.nuget/NuGet

# Copy the repo so restore/build picks up new projects and shared build files
# without requiring Dockerfile path updates.
COPY . .

# Restore with optional secrets:
# - `nuget_config`: authenticated NuGet.Config (Azure Artifacts) to avoid baking creds into layers
RUN --mount=type=secret,id=nuget_config,dst=/root/.nuget/NuGet/NuGet.Config,required=false \
    dotnet restore HL7UnitTests/HL7UnitTests.csproj

RUN dotnet build -c Release HL7UnitTests/HL7UnitTests.csproj --no-restore
RUN chmod +x /src/docker/run-hl7-unittests.sh \
  && ln -sf /src/docker/run-hl7-unittests.sh /usr/local/bin/run-hl7-unittests.sh

ENTRYPOINT ["/usr/local/bin/run-hl7-unittests.sh"]

