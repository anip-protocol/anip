package dev.anip.generated.gtm_operator_contract_20260512235040;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
public class GtmApprovalController {

    @GetMapping({"/gtm/approvals", "/gtm/pipeline/approvals", "/gtm/prioritization/approvals"})
    public Map<String, Object> listApprovals(@RequestParam(name = "status", required = false) String status) {
        List<Map<String, Object>> entries = GtmNativeBackendAdapter.listApprovalRequests(status).stream()
                .map(GtmApprovalController::approvalMap)
                .toList();
        return Map.of("entries", entries);
    }

    @PostMapping({
            "/gtm/approvals/{approvalRequestId}/approve",
            "/gtm/pipeline/approvals/{approvalRequestId}/approve",
            "/gtm/prioritization/approvals/{approvalRequestId}/approve"
    })
    public ResponseEntity<Map<String, Object>> approveRequest(
            @PathVariable String approvalRequestId,
            @RequestHeader(name = "authorization", required = false) String authorization
    ) {
        GtmNativeBackendAdapter.ActorPolicy actor = GtmNativeBackendAdapter.actorFromBearer(authorization);
        GtmNativeBackendAdapter.ApprovalRecord record = GtmNativeBackendAdapter.approveRequest(approvalRequestId, actor);
        if (record == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "approval request not found"));
        }
        return ResponseEntity.ok(Map.of("approval", approvalMap(record)));
    }

    private static Map<String, Object> approvalMap(GtmNativeBackendAdapter.ApprovalRecord record) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("approval_request_id", record.approvalRequestId);
        result.put("capability", record.capability);
        result.put("required_role", record.requiredRole);
        result.put("status", record.status);
        result.put("requested_by", record.requestedBy);
        result.put("approved_by", record.approvedBy);
        result.put("preview", record.preview);
        result.put("created_at", record.createdAt);
        result.put("approved_at", record.approvedAt);
        return result;
    }
}
