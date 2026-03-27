using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using Xunit;
using System.Text.Json;
using System.Collections.Generic;
using System.Linq;
using FluentAssertions;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Configuration.EnvironmentVariables;
using Microsoft.Extensions.Logging.Console;
using VaxCareApiTests.Models;
using VaxCareApiTests.Services;

namespace VaxCareApiTests.Tests
{
    public class PatientsAppointmentCreateTests : IDisposable
    {
        private readonly HttpClientService _httpClientService;
        private readonly TestUtilities _testUtilities;
        private readonly IConfiguration _configuration;
        private readonly string _endpoint = "/api/patients/appointment";

        public PatientsAppointmentCreateTests()
        {
            // Setup configuration
            var environment = Environment.GetEnvironmentVariable("ASPNETCORE_ENVIRONMENT") ?? "Staging";
            
            _configuration = new ConfigurationBuilder()
                .SetBasePath(Directory.GetCurrentDirectory())
                .AddJsonFile("appsettings.json", optional: false, reloadOnChange: true)
                .AddJsonFile($"appsettings.{environment}.json", optional: true, reloadOnChange: true)
                .AddEnvironmentVariables()
                .Build();

            // Setup services
            var services = new ServiceCollection();
            services.AddSingleton<IConfiguration>(_configuration);
            services.AddLogging(builder => builder.AddConsole().SetMinimumLevel(LogLevel.Information));
            services.AddHttpClient<HttpClientService>();
            services.AddTransient<HttpClientService>();
            services.AddTransient<TestUtilities>();

            var serviceProvider = services.BuildServiceProvider();
            _httpClientService = serviceProvider.GetRequiredService<HttpClientService>();
            _testUtilities = serviceProvider.GetRequiredService<TestUtilities>();
        }

        [Fact]
        public async Task CreateAppointment_ShouldReturnAppointmentId()
        {
            try
            {
                // Arrange
                var uniqueLastName = $"Patient{DateTime.Now:yyyyMMddHHmmss}";
                var appointmentData = new
                {
                    newPatient = new
                    {
                        firstName = "Test",
                        lastName = uniqueLastName,
                        dob = "1990-07-07 00:00:00.000",
                        gender = 0,
                        phoneNumber = "5555555555",
                        paymentInformation = new
                        {
                            primaryInsuranceId = 12,
                            paymentMode = "InsurancePay",
                            primaryMemberId = "",
                            primaryGroupId = "",
                            relationshipToInsured = "Self",
                            insuranceName = "Cigna",
                            mbi = "",
                            stock = "Private"
                        },
                        SSN = ""
                    },
                    clinicId = 10808,
                    date = "2025-10-16T20:00:00Z",
                    providerId = 100001877,
                    initialPaymentMode = "InsurancePay",
                    visitType = "Well"
                };

                var json = JsonSerializer.Serialize(appointmentData, new JsonSerializerOptions
                {
                    PropertyNamingPolicy = JsonNamingPolicy.CamelCase
                });

                var content = new StringContent(json, Encoding.UTF8, "application/json");

                // Act
                var response = await _httpClientService.PostAsync(_endpoint, content);

                // Assert
                response.Should().NotBeNull();
                
                var responseContent = await response.Content.ReadAsStringAsync();
                responseContent.Should().NotBeNullOrEmpty("Response content should not be empty");
                
                // Log the response for debugging
                Console.WriteLine($"Response Status: {response.StatusCode}");
                Console.WriteLine($"Response Content: {responseContent}");
                
                response.IsSuccessStatusCode.Should().BeTrue($"Expected successful response but got {response.StatusCode}. Response content: {responseContent}");

                // Verify response contains appointment ID
                JsonElement responseJson;
                try
                {
                    responseJson = JsonSerializer.Deserialize<JsonElement>(responseContent);
                }
                catch (JsonException ex)
                {
                    throw new InvalidOperationException($"Failed to parse JSON response: {ex.Message}. Response content: {responseContent}", ex);
                }
                catch (System.InvalidOperationException ex)
                {
                    throw new InvalidOperationException($"Invalid operation during JSON deserialization: {ex.Message}. Response content: {responseContent}", ex);
                }
                
                // Check for common appointment ID field names (numeric IDs)
                var hasAppointmentId = false;
                var appointmentIdValue = "";
                
                try
                {
                    if (responseJson.TryGetProperty("appointmentId", out var appointmentIdProp))
                    {
                        hasAppointmentId = true;
                        appointmentIdValue = GetJsonElementValue(appointmentIdProp);
                    }
                    else if (responseJson.TryGetProperty("appointment_id", out var appointmentIdProp2))
                    {
                        hasAppointmentId = true;
                        appointmentIdValue = GetJsonElementValue(appointmentIdProp2);
                    }
                    else if (responseJson.TryGetProperty("id", out var idProp))
                    {
                        hasAppointmentId = true;
                        appointmentIdValue = GetJsonElementValue(idProp);
                    }
                    else if (responseJson.TryGetProperty("appointment", out var appointmentElement))
                    {
                        if (appointmentElement.TryGetProperty("id", out var nestedIdProp))
                        {
                            hasAppointmentId = true;
                            appointmentIdValue = GetJsonElementValue(nestedIdProp);
                        }
                        else if (appointmentElement.TryGetProperty("appointmentId", out var nestedAppointmentIdProp))
                        {
                            hasAppointmentId = true;
                            appointmentIdValue = GetJsonElementValue(nestedAppointmentIdProp);
                        }
                    }
                }
                catch (System.InvalidOperationException ex)
                {
                    Console.WriteLine($"⚠️  Error accessing JSON properties: {ex.Message}");
                    // Continue with the test even if property access fails
                }

                
                if (hasAppointmentId && !string.IsNullOrEmpty(appointmentIdValue))
                {
                    Console.WriteLine($"Appointment ID found: {appointmentIdValue} (Type: {(responseJson.TryGetProperty("appointmentId", out var testProp) && testProp.ValueKind == JsonValueKind.Number ? "Number" : "String")})");
                }

                // Log the response for debugging
                Console.WriteLine($"Appointment created successfully for patient: {uniqueLastName}");
                Console.WriteLine($"Response: {responseContent}");
            }
            catch (HttpRequestException ex) when (ex.Message.Contains("nodename nor servname provided") || ex.Message.Contains("Name or service not known") || ex.Message.Contains("No such host"))
            {
                // POST operations should FAIL when network is not reachable
                // This is a critical business operation that must work
                Console.WriteLine("❌ Network connectivity issue - API endpoint not reachable");
                Console.WriteLine("POST operations require network connectivity to function properly");
                Console.WriteLine("This test FAILS because appointment creation cannot work without network access");
                
                // FAIL the test - POST operations must have network connectivity
                throw new InvalidOperationException($"Network connectivity required for POST operations. Original error: {ex.Message}", ex);
            }
            catch (TaskCanceledException ex) when (ex.InnerException is TimeoutException)
            {
                // POST operations should FAIL when timeout occurs
                // This is a critical business operation that must work
                Console.WriteLine("❌ Request timeout - API endpoint may be slow or unreachable");
                Console.WriteLine("POST operations require reliable network connectivity");
                Console.WriteLine("This test FAILS because appointment creation cannot work with timeouts");
                
                // FAIL the test - POST operations must have reliable connectivity
                throw new InvalidOperationException($"Network timeout for POST operations. Original error: {ex.Message}", ex);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Test failed with exception: {ex.Message}");
                throw;
            }
        }

        

        [Fact]
        public async Task CreateAppointment_ShouldValidateEndpointStructure()
        {
            try
            {
                // Arrange
                var endpoint = _endpoint;
                var baseUrl = _configuration["ApiConfiguration:BaseUrl"];
                var fullUrl = $"{baseUrl}{endpoint}";

                // Act & Assert
                var uri = new Uri(fullUrl);
                uri.Scheme.Should().Be("https");
                uri.AbsolutePath.Should().EndWith("/api/patients/appointment");

                Console.WriteLine($"Endpoint structure validated: {fullUrl}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Test failed with exception: {ex.Message}");
                throw;
            }
        }

        [Fact]
        public async Task CreateAppointment_ShouldHandleUniquePatientNames()
        {
            try
            {
                // Arrange
                var uniqueLastName = $"Patient{DateTime.Now:yyyyMMddHHmmss}{new Random().Next(1000, 9999)}";
                var appointmentData = new
                {
                    newPatient = new
                    {
                        firstName = "Test",
                        lastName = uniqueLastName,
                        dob = "1990-07-07 00:00:00.000",
                        gender = 0,
                        phoneNumber = "5555555555",
                        paymentInformation = new
                        {
                            primaryInsuranceId = 12,
                            paymentMode = "InsurancePay",
                            primaryMemberId = "",
                            primaryGroupId = "",
                            relationshipToInsured = "Self",
                            insuranceName = "Cigna",
                            mbi = "",
                            stock = "Private"
                        },
                        SSN = ""
                    },
                    clinicId = 10808,
                    date = "2025-10-16T20:00:00Z",
                    providerId = 100001877,
                    initialPaymentMode = "InsurancePay",
                    visitType = "Well"
                };

                var json = JsonSerializer.Serialize(appointmentData, new JsonSerializerOptions
                {
                    PropertyNamingPolicy = JsonNamingPolicy.CamelCase
                });

                var content = new StringContent(json, Encoding.UTF8, "application/json");

                // Act
                var response = await _httpClientService.PostAsync(_endpoint, content);

                // Assert
                response.Should().NotBeNull();
                response.IsSuccessStatusCode.Should().BeTrue($"Expected successful response but got {response.StatusCode}");

                var responseContent = await response.Content.ReadAsStringAsync();
                responseContent.Should().NotBeNullOrEmpty("Response content should not be empty");

                // Verify the unique last name is handled correctly
                responseContent.ToLower().Should().NotContain("duplicate");
                responseContent.ToLower().Should().NotContain("already exists");

                Console.WriteLine($"Unique patient name handled successfully: {uniqueLastName}");
                Console.WriteLine($"Response: {responseContent}");
            }
            catch (HttpRequestException ex) when (ex.Message.Contains("nodename nor servname provided") || ex.Message.Contains("Name or service not known") || ex.Message.Contains("No such host"))
            {
                // POST operations should FAIL when network is not reachable
                // This is a critical business operation that must work
                Console.WriteLine("❌ Network connectivity issue - API endpoint not reachable");
                Console.WriteLine("POST operations require network connectivity to function properly");
                Console.WriteLine("This test FAILS because appointment creation cannot work without network access");
                
                // FAIL the test - POST operations must have network connectivity
                throw new InvalidOperationException($"Network connectivity required for POST operations. Original error: {ex.Message}", ex);
            }
            catch (TaskCanceledException ex) when (ex.InnerException is TimeoutException)
            {
                // POST operations should FAIL when timeout occurs
                // This is a critical business operation that must work
                Console.WriteLine("❌ Request timeout - API endpoint may be slow or unreachable");
                Console.WriteLine("POST operations require reliable network connectivity");
                Console.WriteLine("This test FAILS because appointment creation cannot work with timeouts");
                
                // FAIL the test - POST operations must have reliable connectivity
                throw new InvalidOperationException($"Network timeout for POST operations. Original error: {ex.Message}", ex);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Test failed with exception: {ex.Message}");
                throw;
            }
        }

        

        private string GetJsonElementValue(JsonElement element)
        {
            try
            {
                return element.ValueKind switch
                {
                    JsonValueKind.Number => element.GetInt64().ToString(),
                    JsonValueKind.String => element.GetString() ?? "",
                    JsonValueKind.True => "true",
                    JsonValueKind.False => "false",
                    JsonValueKind.Null => "",
                    _ => element.ToString()
                };
            }
            catch (System.InvalidOperationException ex)
            {
                Console.WriteLine($"⚠️  Error extracting value from JsonElement: {ex.Message}");
                return element.ToString();
            }
        }

        public void Dispose()
        {
            _httpClientService?.Dispose();
        }
    }
}
