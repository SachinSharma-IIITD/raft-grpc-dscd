from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class LogEntry(_message.Message):
    __slots__ = ("term", "index", "data")
    TERM_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    term: int
    index: int
    data: str
    def __init__(self, term: _Optional[int] = ..., index: _Optional[int] = ..., data: _Optional[str] = ...) -> None: ...

class AppendEntriesReq(_message.Message):
    __slots__ = ("term", "leader_id", "prev_log_index", "prev_log_term", "entries", "leader_commit", "leader_lease")
    TERM_FIELD_NUMBER: _ClassVar[int]
    LEADER_ID_FIELD_NUMBER: _ClassVar[int]
    PREV_LOG_INDEX_FIELD_NUMBER: _ClassVar[int]
    PREV_LOG_TERM_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    LEADER_COMMIT_FIELD_NUMBER: _ClassVar[int]
    LEADER_LEASE_FIELD_NUMBER: _ClassVar[int]
    term: int
    leader_id: int
    prev_log_index: int
    prev_log_term: int
    entries: _containers.RepeatedCompositeFieldContainer[LogEntry]
    leader_commit: int
    leader_lease: int
    def __init__(self, term: _Optional[int] = ..., leader_id: _Optional[int] = ..., prev_log_index: _Optional[int] = ..., prev_log_term: _Optional[int] = ..., entries: _Optional[_Iterable[_Union[LogEntry, _Mapping]]] = ..., leader_commit: _Optional[int] = ..., leader_lease: _Optional[int] = ...) -> None: ...

class AppendEntriesResponse(_message.Message):
    __slots__ = ("term", "success", "last_log_index")
    TERM_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    LAST_LOG_INDEX_FIELD_NUMBER: _ClassVar[int]
    term: int
    success: bool
    last_log_index: int
    def __init__(self, term: _Optional[int] = ..., success: bool = ..., last_log_index: _Optional[int] = ...) -> None: ...

class RequestVoteReq(_message.Message):
    __slots__ = ("term", "candidate_id", "last_log_index", "last_log_term")
    TERM_FIELD_NUMBER: _ClassVar[int]
    CANDIDATE_ID_FIELD_NUMBER: _ClassVar[int]
    LAST_LOG_INDEX_FIELD_NUMBER: _ClassVar[int]
    LAST_LOG_TERM_FIELD_NUMBER: _ClassVar[int]
    term: int
    candidate_id: int
    last_log_index: int
    last_log_term: int
    def __init__(self, term: _Optional[int] = ..., candidate_id: _Optional[int] = ..., last_log_index: _Optional[int] = ..., last_log_term: _Optional[int] = ...) -> None: ...

class RequestVoteResponse(_message.Message):
    __slots__ = ("term", "vote_granted", "leader_lease")
    TERM_FIELD_NUMBER: _ClassVar[int]
    VOTE_GRANTED_FIELD_NUMBER: _ClassVar[int]
    LEADER_LEASE_FIELD_NUMBER: _ClassVar[int]
    term: int
    vote_granted: bool
    leader_lease: int
    def __init__(self, term: _Optional[int] = ..., vote_granted: bool = ..., leader_lease: _Optional[int] = ...) -> None: ...

class GetReq(_message.Message):
    __slots__ = ("key",)
    KEY_FIELD_NUMBER: _ClassVar[int]
    key: str
    def __init__(self, key: _Optional[str] = ...) -> None: ...

class GetResponse(_message.Message):
    __slots__ = ("success", "value", "leader_id")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    LEADER_ID_FIELD_NUMBER: _ClassVar[int]
    success: bool
    value: str
    leader_id: int
    def __init__(self, success: bool = ..., value: _Optional[str] = ..., leader_id: _Optional[int] = ...) -> None: ...

class SetReq(_message.Message):
    __slots__ = ("key", "value")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    key: str
    value: str
    def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class SetResponse(_message.Message):
    __slots__ = ("success", "leader_id")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    LEADER_ID_FIELD_NUMBER: _ClassVar[int]
    success: bool
    leader_id: int
    def __init__(self, success: bool = ..., leader_id: _Optional[int] = ...) -> None: ...
