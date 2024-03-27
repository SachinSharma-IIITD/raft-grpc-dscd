This dump file MUST contain the following print statements:

Before the leader sends heartbeats to the followers:

`Leader {NodeID of Leader} sending heartbeat & Renewing Lease`

If the leader fails to renew its lease:

`Leader {NodeID of Leader} lease renewal failed. Stepping Down.`

When a new leader is selected, it waits for the old leader’s timeout to end:

`New Leader waiting for Old Leader Lease to timeout.`

When the election timer times out for any node:

`Node {NodeID} election timer timed out, Starting election.`

Whenever a node becomes a leader:

`Node {NodeID} became the leader for term {TermNumber}.`

When the follower node has crashed:

`Error occurred while sending RPC to Node {followerNodeID}.`

Whenever a follower node successfully commits (not appends) an entry to its logs:

`Node {NodeID of follower} (follower) committed the entry {entry operation} to the state machine.`

Example of an entry operation: `SET x 6`
Whenever a leader node receives a request (SET or GET) from the client:

`Node {NodeID of leader} (leader) received an {entry operation} request.`

Whenever a leader node successfully commits (not appends) an entry to its logs:

`Node {NodeID of leader} (leader) committed the entry {entry operation} to the state machine.`

Whenever a follower node receives and accepts an append entry request and appends the operation to its logs:

`Node {NodeID of follower} accepted AppendEntries RPC from {NodeID of leader}.`

Whenever a follower node receives and rejects an append entry request:

`Node {NodeID of follower} rejected AppendEntries RPC from {NodeID of leader}.`

Whenever a node grants a vote to a candidate in a particular term:

`Vote granted for Node {Candidate NodeID} in term {term of the vote}.`

Whenever a node denies a vote to a candidate in a particular term:

`Vote denied for Node {Candidate NodeID} in term {term of the vote}.`

Whenever a leader node steps down and becomes a follower:

`{NodeID} Stepping down`