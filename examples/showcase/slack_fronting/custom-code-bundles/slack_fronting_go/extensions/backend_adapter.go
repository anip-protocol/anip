package extensions

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"

	"{{ANIP_GO_MODULE_PATH}}/generated"
)

type BackendInvocationContext struct {
	RootPrincipal string
	ApprovalGrant string
}

type BackendAdapter interface {
	Execute(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, adapterInput map[string]any, context BackendInvocationContext) (map[string]any, error)
}

type slackBackendAdapter struct{}

func CreateDefaultBackendAdapter() BackendAdapter {
	return slackBackendAdapter{}
}

func (slackBackendAdapter) Execute(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, context BackendInvocationContext) (map[string]any, error) {
	if len(plan.UnresolvedRequiredBackendInputs) > 0 {
		return result(capability, plan, "backend_input_incomplete", map[string]any{"unresolved_required_backend_inputs": plan.UnresolvedRequiredBackendInputs}), nil
	}
	token := strings.TrimSpace(os.Getenv("SLACK_BOT_TOKEN"))
	switch capability.CapabilityID {
	case "slack.channel.read_context":
		if token == "" {
			return result(capability, plan, "backend_not_configured", map[string]any{"missing_env": "SLACK_BOT_TOKEN"}), nil
		}
		return readChannelContext(capability, plan, params, token), nil
	case "slack.thread.summarize":
		if token == "" {
			return result(capability, plan, "backend_not_configured", map[string]any{"missing_env": "SLACK_BOT_TOKEN"}), nil
		}
		return readThreadContext(capability, plan, params, token), nil
	case "slack.message.prepare", "slack.incident_update.prepare", "slack.announcement.request":
		return prepareOrSendMessage(capability, plan, params, token, context), nil
	default:
		return result(capability, plan, "backend_execution_stub", map[string]any{"note": "No Slack custom handler is registered for this capability."}), nil
	}
}

func readChannelContext(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string) map[string]any {
	channelID := text(params["channel_id"])
	if !channelAllowed(channelID) {
		return restricted(capability, plan, channelID)
	}
	limit := boundedLimit(params["limit"], 20, 50)
	query := strings.ToLower(text(params["query"]))
	payload := slackPost(token, "conversations.history", map[string]any{"channel": channelID, "limit": limit})
	if payload["ok"] != true {
		return backendError(capability, plan, payload)
	}
	messages := summarizeMessages(payload["messages"])
	if query != "" {
		filtered := []map[string]any{}
		for _, message := range messages {
			if strings.Contains(strings.ToLower(text(message["text"])), query) {
				filtered = append(filtered, message)
			}
		}
		messages = filtered
	}
	if len(messages) > limit {
		messages = messages[:limit]
	}
	return result(capability, plan, "completed", map[string]any{"result": map[string]any{"messages": messages, "count": len(messages), "channel_id": channelID}})
}

func readThreadContext(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string) map[string]any {
	channelID := text(params["channel_id"])
	if !channelAllowed(channelID) {
		return restricted(capability, plan, channelID)
	}
	threadTS := text(params["thread_ts"])
	limit := boundedLimit(params["limit"], 50, 100)
	payload := slackPost(token, "conversations.replies", map[string]any{"channel": channelID, "ts": threadTS, "limit": limit})
	if payload["ok"] != true {
		return backendError(capability, plan, payload)
	}
	messages := summarizeMessages(payload["messages"])
	return result(capability, plan, "completed", map[string]any{"result": map[string]any{"messages": messages, "count": len(messages), "channel_id": channelID, "thread_ts": threadTS}})
}

func prepareOrSendMessage(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, params map[string]any, token string, context BackendInvocationContext) map[string]any {
	channelID := text(params["channel_id"])
	if !channelAllowed(channelID) {
		return restricted(capability, plan, channelID)
	}
	body := map[string]any{"channel": channelID, "text": messageText(capability, params)}
	if threadTS := text(params["thread_ts"]); threadTS != "" {
		body["thread_ts"] = threadTS
	}
	preview := result(capability, plan, "prepared", map[string]any{
		"approval_required": true,
		"mutation_performed": false,
		"slack_action": "chat.postMessage",
		"post_message_request": map[string]any{"method": "POST", "path": "/api/chat.postMessage", "body": body},
		"note": "Prepared a Slack message payload. No Slack message was sent.",
	})
	if os.Getenv("ANIP_SLACK_ALLOW_SEND") != "true" || strings.TrimSpace(context.ApprovalGrant) == "" {
		return preview
	}
	if token == "" {
		preview["execution_status"] = "backend_error"
		preview["slack_error"] = map[string]any{"ok": false, "error": "missing_slack_token"}
		return preview
	}
	posted := slackPost(token, "chat.postMessage", body)
	if posted["ok"] != true {
		preview["execution_status"] = "backend_error"
		preview["slack_error"] = posted
		return preview
	}
	preview["execution_status"] = "completed"
	preview["approval_required"] = false
	preview["mutation_performed"] = true
	preview["posted_message"] = map[string]any{"channel": posted["channel"], "ts": posted["ts"]}
	preview["approval_grant_id"] = context.ApprovalGrant
	preview["note"] = "Sent Slack message after the ANIP runtime validated and reserved an approval grant."
	return preview
}

func slackPost(token, path string, body map[string]any) map[string]any {
	values := url.Values{}
	for key, value := range body {
		if value != nil {
			values.Set(key, text(value))
		}
	}
	request, _ := http.NewRequest("POST", "https://slack.com/api/"+path, strings.NewReader(values.Encode()))
	request.Header.Set("Accept", "application/json")
	request.Header.Set("Authorization", "Bearer "+token)
	request.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return map[string]any{"ok": false, "error": "slack_http_error", "detail": err.Error()}
	}
	defer response.Body.Close()
	var payload map[string]any
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		return map[string]any{"ok": false, "error": "slack_decode_error", "detail": err.Error()}
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return map[string]any{"ok": false, "error": "slack_http_error", "status": response.StatusCode, "detail": payload}
	}
	return payload
}

func messageText(capability generated.GeneratedCapabilityRuntimeMetadata, params map[string]any) string {
	switch capability.CapabilityID {
	case "slack.incident_update.prepare":
		parts := []string{fmt.Sprintf("Incident %s: %s", text(params["incident_id"]), text(params["status"])), text(params["summary"])}
		if next := text(params["next_update_time"]); next != "" {
			parts = append(parts, "Next update: "+next)
		}
		return strings.Join(nonEmpty(parts), "\n")
	case "slack.announcement.request":
		audience := text(params["audience"])
		prefix := ""
		if audience != "" {
			prefix = "[" + audience + "] "
		}
		return prefix + text(params["announcement"])
	default:
		return text(params["text"])
	}
}

func summarizeMessages(value any) []map[string]any {
	items, _ := value.([]any)
	result := make([]map[string]any, 0, len(items))
	for _, item := range items {
		if message, ok := item.(map[string]any); ok {
			result = append(result, map[string]any{"ts": message["ts"], "user": firstNonNil(message["user"], message["bot_id"]), "text": message["text"], "thread_ts": message["thread_ts"]})
		}
	}
	return result
}

func result(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, status string, extra map[string]any) map[string]any {
	payload := map[string]any{"execution_status": status, "capability_id": capability.CapabilityID, "selected_backend": plan.SelectedBinding, "semantic_input": plan.SemanticInput, "backend_input_contract": plan.BackendInputContract}
	for key, value := range extra {
		payload[key] = value
	}
	return payload
}

func restricted(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, channelID string) map[string]any {
	return result(capability, plan, "restricted", map[string]any{"channel_id": channelID, "reason": "Slack channel is outside the configured ANIP channel policy."})
}

func backendError(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, payload map[string]any) map[string]any {
	return result(capability, plan, "backend_error", map[string]any{"slack_error": payload})
}

func boundedLimit(value any, defaultValue, maximum int) int {
	limit, err := strconv.Atoi(text(value))
	if err != nil {
		limit = defaultValue
	}
	if limit < 1 {
		return 1
	}
	if limit > maximum {
		return maximum
	}
	return limit
}

func channelAllowed(channelID string) bool {
	blocked := csvEnv("ANIP_SLACK_BLOCKED_CHANNELS")
	allowed := csvEnv("ANIP_SLACK_ALLOWED_CHANNELS")
	if contains(blocked, channelID) {
		return false
	}
	return len(allowed) == 0 || contains(allowed, channelID)
}

func csvEnv(name string) []string {
	result := []string{}
	for _, item := range strings.Split(os.Getenv(name), ",") {
		if value := strings.TrimSpace(item); value != "" && !contains(result, value) {
			result = append(result, value)
		}
	}
	return result
}

func text(value any) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(value))
}

func firstNonNil(values ...any) any {
	for _, value := range values {
		if value != nil && text(value) != "" {
			return value
		}
	}
	return nil
}

func nonEmpty(values []string) []string {
	result := []string{}
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			result = append(result, value)
		}
	}
	return result
}

func contains(values []string, candidate string) bool {
	for _, value := range values {
		if value == candidate {
			return true
		}
	}
	return false
}

var BackendAdapterInstance = CreateDefaultBackendAdapter()
