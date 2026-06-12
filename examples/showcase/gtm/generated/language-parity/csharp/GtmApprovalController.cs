using Microsoft.AspNetCore.Mvc;

namespace GTMPipelineQ2Review;

[ApiController]
public sealed class GtmApprovalController : ControllerBase
{
    [HttpGet("/gtm/approvals")]
    [HttpGet("/gtm/pipeline/approvals")]
    [HttpGet("/gtm/prioritization/approvals")]
    public Dictionary<string, object?> List([FromQuery] string? status = null)
    {
        return new Dictionary<string, object?>
        {
            ["entries"] = GtmNativeBackendAdapter.ListApprovals(status).Select(ToWire).ToList(),
        };
    }

    [HttpPost("/gtm/approvals/{approvalRequestId}/approve")]
    [HttpPost("/gtm/pipeline/approvals/{approvalRequestId}/approve")]
    [HttpPost("/gtm/prioritization/approvals/{approvalRequestId}/approve")]
    public IActionResult Approve(string approvalRequestId, [FromHeader(Name = "authorization")] string? authorization = null)
    {
        var record = GtmNativeBackendAdapter.Approve(approvalRequestId, GtmNativeBackendAdapter.ActorFromBearer(authorization));
        if (record is null)
        {
            return NotFound(new Dictionary<string, object?> { ["error"] = "approval request not found" });
        }
        return Ok(new Dictionary<string, object?> { ["approval"] = ToWire(record) });
    }

    private static Dictionary<string, object?> ToWire(ApprovalRecord record)
    {
        return new Dictionary<string, object?>
        {
            ["approval_request_id"] = record.ApprovalRequestId,
            ["capability"] = record.Capability,
            ["required_role"] = record.RequiredRole,
            ["status"] = record.Status,
            ["requested_by"] = record.RequestedBy,
            ["approved_by"] = record.ApprovedBy,
            ["preview"] = record.Preview,
            ["created_at"] = record.CreatedAt,
            ["approved_at"] = record.ApprovedAt,
        };
    }
}
