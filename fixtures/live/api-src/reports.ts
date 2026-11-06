// Fixture: route definitions the access test finds by itself (tenant_routes). Not real code.
app.get("/v1/tenants/:tenantId/reports", listReports);
app.delete("/v1/tenants/:tenantId/reports/:reportId", deleteReport);
