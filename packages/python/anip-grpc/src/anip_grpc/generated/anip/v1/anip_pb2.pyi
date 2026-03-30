from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AnipFailure(_message.Message):
    __slots__ = ("type", "detail", "resolution_json", "retry")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DETAIL_FIELD_NUMBER: _ClassVar[int]
    RESOLUTION_JSON_FIELD_NUMBER: _ClassVar[int]
    RETRY_FIELD_NUMBER: _ClassVar[int]
    type: str
    detail: str
    resolution_json: str
    retry: bool
    def __init__(self, type: _Optional[str] = ..., detail: _Optional[str] = ..., resolution_json: _Optional[str] = ..., retry: bool = ...) -> None: ...

class DiscoveryRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DiscoveryResponse(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class ManifestRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ManifestResponse(_message.Message):
    __slots__ = ("manifest_json", "signature")
    MANIFEST_JSON_FIELD_NUMBER: _ClassVar[int]
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    manifest_json: str
    signature: str
    def __init__(self, manifest_json: _Optional[str] = ..., signature: _Optional[str] = ...) -> None: ...

class JwksRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class JwksResponse(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class IssueTokenRequest(_message.Message):
    __slots__ = ("subject", "scope", "capability", "purpose_parameters_json", "parent_token", "ttl_hours", "caller_class")
    SUBJECT_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    CAPABILITY_FIELD_NUMBER: _ClassVar[int]
    PURPOSE_PARAMETERS_JSON_FIELD_NUMBER: _ClassVar[int]
    PARENT_TOKEN_FIELD_NUMBER: _ClassVar[int]
    TTL_HOURS_FIELD_NUMBER: _ClassVar[int]
    CALLER_CLASS_FIELD_NUMBER: _ClassVar[int]
    subject: str
    scope: _containers.RepeatedScalarFieldContainer[str]
    capability: str
    purpose_parameters_json: str
    parent_token: str
    ttl_hours: int
    caller_class: str
    def __init__(self, subject: _Optional[str] = ..., scope: _Optional[_Iterable[str]] = ..., capability: _Optional[str] = ..., purpose_parameters_json: _Optional[str] = ..., parent_token: _Optional[str] = ..., ttl_hours: _Optional[int] = ..., caller_class: _Optional[str] = ...) -> None: ...

class IssueTokenResponse(_message.Message):
    __slots__ = ("issued", "token_id", "token", "expires", "failure")
    ISSUED_FIELD_NUMBER: _ClassVar[int]
    TOKEN_ID_FIELD_NUMBER: _ClassVar[int]
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_FIELD_NUMBER: _ClassVar[int]
    FAILURE_FIELD_NUMBER: _ClassVar[int]
    issued: bool
    token_id: str
    token: str
    expires: str
    failure: AnipFailure
    def __init__(self, issued: bool = ..., token_id: _Optional[str] = ..., token: _Optional[str] = ..., expires: _Optional[str] = ..., failure: _Optional[_Union[AnipFailure, _Mapping]] = ...) -> None: ...

class PermissionsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PermissionsResponse(_message.Message):
    __slots__ = ("success", "json", "failure")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    JSON_FIELD_NUMBER: _ClassVar[int]
    FAILURE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    json: str
    failure: AnipFailure
    def __init__(self, success: bool = ..., json: _Optional[str] = ..., failure: _Optional[_Union[AnipFailure, _Mapping]] = ...) -> None: ...

class InvokeRequest(_message.Message):
    __slots__ = ("capability", "parameters_json", "client_reference_id", "task_id", "parent_invocation_id")
    CAPABILITY_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_JSON_FIELD_NUMBER: _ClassVar[int]
    CLIENT_REFERENCE_ID_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    capability: str
    parameters_json: str
    client_reference_id: str
    task_id: str
    parent_invocation_id: str
    def __init__(self, capability: _Optional[str] = ..., parameters_json: _Optional[str] = ..., client_reference_id: _Optional[str] = ..., task_id: _Optional[str] = ..., parent_invocation_id: _Optional[str] = ...) -> None: ...

class InvokeResponse(_message.Message):
    __slots__ = ("success", "invocation_id", "client_reference_id", "result_json", "cost_actual_json", "failure", "task_id", "parent_invocation_id")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_REFERENCE_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_JSON_FIELD_NUMBER: _ClassVar[int]
    COST_ACTUAL_JSON_FIELD_NUMBER: _ClassVar[int]
    FAILURE_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    success: bool
    invocation_id: str
    client_reference_id: str
    result_json: str
    cost_actual_json: str
    failure: AnipFailure
    task_id: str
    parent_invocation_id: str
    def __init__(self, success: bool = ..., invocation_id: _Optional[str] = ..., client_reference_id: _Optional[str] = ..., result_json: _Optional[str] = ..., cost_actual_json: _Optional[str] = ..., failure: _Optional[_Union[AnipFailure, _Mapping]] = ..., task_id: _Optional[str] = ..., parent_invocation_id: _Optional[str] = ...) -> None: ...

class InvokeEvent(_message.Message):
    __slots__ = ("progress", "completed", "failed")
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_FIELD_NUMBER: _ClassVar[int]
    FAILED_FIELD_NUMBER: _ClassVar[int]
    progress: ProgressEvent
    completed: CompletedEvent
    failed: FailedEvent
    def __init__(self, progress: _Optional[_Union[ProgressEvent, _Mapping]] = ..., completed: _Optional[_Union[CompletedEvent, _Mapping]] = ..., failed: _Optional[_Union[FailedEvent, _Mapping]] = ...) -> None: ...

class ProgressEvent(_message.Message):
    __slots__ = ("invocation_id", "payload_json")
    INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_JSON_FIELD_NUMBER: _ClassVar[int]
    invocation_id: str
    payload_json: str
    def __init__(self, invocation_id: _Optional[str] = ..., payload_json: _Optional[str] = ...) -> None: ...

class CompletedEvent(_message.Message):
    __slots__ = ("invocation_id", "client_reference_id", "result_json", "cost_actual_json", "task_id", "parent_invocation_id")
    INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_REFERENCE_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_JSON_FIELD_NUMBER: _ClassVar[int]
    COST_ACTUAL_JSON_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    invocation_id: str
    client_reference_id: str
    result_json: str
    cost_actual_json: str
    task_id: str
    parent_invocation_id: str
    def __init__(self, invocation_id: _Optional[str] = ..., client_reference_id: _Optional[str] = ..., result_json: _Optional[str] = ..., cost_actual_json: _Optional[str] = ..., task_id: _Optional[str] = ..., parent_invocation_id: _Optional[str] = ...) -> None: ...

class FailedEvent(_message.Message):
    __slots__ = ("invocation_id", "client_reference_id", "failure", "task_id", "parent_invocation_id")
    INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_REFERENCE_ID_FIELD_NUMBER: _ClassVar[int]
    FAILURE_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    invocation_id: str
    client_reference_id: str
    failure: AnipFailure
    task_id: str
    parent_invocation_id: str
    def __init__(self, invocation_id: _Optional[str] = ..., client_reference_id: _Optional[str] = ..., failure: _Optional[_Union[AnipFailure, _Mapping]] = ..., task_id: _Optional[str] = ..., parent_invocation_id: _Optional[str] = ...) -> None: ...

class QueryAuditRequest(_message.Message):
    __slots__ = ("capability", "since", "invocation_id", "client_reference_id", "event_class", "limit", "task_id", "parent_invocation_id")
    CAPABILITY_FIELD_NUMBER: _ClassVar[int]
    SINCE_FIELD_NUMBER: _ClassVar[int]
    INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_REFERENCE_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_CLASS_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_INVOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    capability: str
    since: str
    invocation_id: str
    client_reference_id: str
    event_class: str
    limit: int
    task_id: str
    parent_invocation_id: str
    def __init__(self, capability: _Optional[str] = ..., since: _Optional[str] = ..., invocation_id: _Optional[str] = ..., client_reference_id: _Optional[str] = ..., event_class: _Optional[str] = ..., limit: _Optional[int] = ..., task_id: _Optional[str] = ..., parent_invocation_id: _Optional[str] = ...) -> None: ...

class QueryAuditResponse(_message.Message):
    __slots__ = ("success", "json", "failure")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    JSON_FIELD_NUMBER: _ClassVar[int]
    FAILURE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    json: str
    failure: AnipFailure
    def __init__(self, success: bool = ..., json: _Optional[str] = ..., failure: _Optional[_Union[AnipFailure, _Mapping]] = ...) -> None: ...

class ListCheckpointsRequest(_message.Message):
    __slots__ = ("limit",)
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    limit: int
    def __init__(self, limit: _Optional[int] = ...) -> None: ...

class ListCheckpointsResponse(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...

class GetCheckpointRequest(_message.Message):
    __slots__ = ("id", "include_proof", "leaf_index", "consistency_from")
    ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_PROOF_FIELD_NUMBER: _ClassVar[int]
    LEAF_INDEX_FIELD_NUMBER: _ClassVar[int]
    CONSISTENCY_FROM_FIELD_NUMBER: _ClassVar[int]
    id: str
    include_proof: bool
    leaf_index: int
    consistency_from: str
    def __init__(self, id: _Optional[str] = ..., include_proof: bool = ..., leaf_index: _Optional[int] = ..., consistency_from: _Optional[str] = ...) -> None: ...

class GetCheckpointResponse(_message.Message):
    __slots__ = ("json",)
    JSON_FIELD_NUMBER: _ClassVar[int]
    json: str
    def __init__(self, json: _Optional[str] = ...) -> None: ...
