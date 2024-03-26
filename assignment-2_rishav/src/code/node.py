import grpc
from concurrent import futures
import time
from threading import Timer
# import raft_pb2
from raft_pb2 import RequestVoteReq, RequestVoteResponse, AppendEntriesReq, AppendEntriesResponse, LogEntry, ClientResponse
import raft_pb2_grpc
import sys
from timer import CountDownTimer
import threading
import random

_MAX_ELECTION_TIMEOUT__ = 10
_HEARTBEAT_TIMEOUT__ = 5
_NUMBER_OF_NODES_IN_CONSENSUS__ = 3
_IP_ADDRESS_LIST = ['127.0.0.1:8000', '127.0.0.1:8001', '127.0.0.1:8002']
__ID__ = int(sys.argv[1])


class Raft(raft_pb2_grpc.RaftServicer):
    def __init__(self):
        # Persistent state on all servers
        self.current_term = 0
        self.voted_for = None
        self.log = []
        # stores data in the form of tuple (command, term)

        # Volatile state on all servers
        self.commit_index = 0
        self.last_applied = 0

        # Volatile state on leaders
        self.next_index = []
        self.match_index = []

        self.election_timeout = CountDownTimer(MAX_T=_MAX_ELECTION_TIMEOUT__, type='random')
        self.heartbeat_timer = CountDownTimer(MAX_T=_HEARTBEAT_TIMEOUT__, type='fixed')

        # keep the status of the server (follower, candidate, leader)
        self.current_state = "follower"
        self.votes = 0
        self.stop_thread = False

    def RequestVote(self, request, context):
        print("---------------------------------")
        print(
            f"Received vote request from {request.candidate_id} {request.term} {self.current_term} {self.voted_for}")
        print("---------------------------------")
        if request.term < self.current_term:
            return RequestVoteResponse(term=self.current_term, vote_granted=False)

        # in request received request from a node with a term greater than the current term, then update the current term
        elif request.term > self.current_term:
            self.current_term = request.term
            self.voted_for = None
            self.current_state = "follower"

        if self.voted_for is None or self.voted_for == request.candidate_id:
            # Check if candidate's log is at least as up-to-date as receiver's log
            if (len(self.log) == 0 or self.log[-1].term < request.last_log_term) or (self.log[-1].term == request.last_log_term and len(self.log) <= request.last_log_index):
                self.voted_for = request.candidate_id
                print("vote granted")
                return RequestVoteResponse(term=self.current_term, vote_granted=True)
        print("vote denied")
        return RequestVoteResponse(term=self.current_term, vote_granted=False)

    def AppendEntries(self, request, context):
        print("---------------------------------")
        print(
            f"Received append entries from {request.leader_id} {request.term} {request.prev_log_index}")
        print("---------------------------------")
        self.election_timeout.restart_timer()

        if (request.term > self.current_term):
            self.current_state = "follower"
            self.current_term = request.term
            self.voted_for = None

        # this is not part of raft (for testing purpose only (over to sachin))
        # if (request.entries == []):
        #     return AppendEntriesResponse(term=self.current_term, success=True)

        # if the term of the request is less than the current term, then reject the request
        # if request.term < self.current_term:
        #     return AppendEntriesResponse(term=self.current_term, success=False)
        # else:
        #     self.current_term = request.term
        #     self.voted_for = None

        if request.term == self.current_term:
            print('Cur log len: ', len(self.log))

            if (len(self.log) > request.prev_log_index):
                if not len(self.log) or (request.prev_log_index == 0 or self.log[request.prev_log_index].term == request.prev_log_term):
                    self.log = self.log[:request.prev_log_index]
                    self.log.extend(request.entries)

                    if request.leader_commit > self.commit_index:
                        self.commit_index = min(
                            request.leader_commit, len(self.log) - 1)

                    print('Success')
                    print(self.log)
                    return AppendEntriesResponse(term=self.current_term, success=True)

        return AppendEntriesResponse(term=self.current_term, success=False)
        # if len(self.log) == 0 and request.prev_log_index >= 0:
        #     return AppendEntriesResponse(term=self.current_term, success=False)

        # if len(self.log) > 0 and len(self.log) < request.prev_log_index + 1 or self.log[request.prev_log_index].term != request.prev_log_term:
        #     return AppendEntriesResponse(term=self.current_term, success=False)
        # else:
        #     self.log = self.log[:request.prev_log_index + 1]
        # if (len(request.entries) > 0):
        #     self.log.extend(request.entries)

        # if request.leader_commit > self.commit_index:
        #     self.commit_index = min(request.leader_commit, len(self.log) - 1)
        # return AppendEntriesResponse(term=self.current_term, success=True)

    def Append(self, request, context):
        if self.current_state != "leader":
            return ClientResponse(success=False)
        self.log.append((request.data, self.current_term))

        self.heartbeat_timer.restart_timer()
        self.send_heart_beats(request.data)

        threads = []
        for i in range(_NUMBER_OF_NODES_IN_CONSENSUS__):
            try:
                if (i == __ID__):
                    continue
                # IP address of the node
                IP_ADDRESS = _IP_ADDRESS_LIST[i]

                t = threading.Thread(
                    target=self.append_parallel, args=(IP_ADDRESS, request,))
                t.start()

            except Exception as e:
                print(f"Node {_IP_ADDRESS_LIST[i]} is busy or not available")
                continue

    def append_parallel(self, IP_ADDRESS, request):

        try:
            channel = grpc.insecure_channel(IP_ADDRESS)
            stub = raft_pb2_grpc.RaftStub(channel)

            lst_lng_t = 0
            if (len(self.log) > 0):
                lst_lng_t = self.log[-1][1]

            response = stub.AppendEntries(AppendEntriesReq(term=self.current_term, leader_id=__ID__, prev_log_index=len(
                self.log)-2, prev_log_term=self.log[-2][1], entries=[LogEntry(term=self.current_term, index=len(self.log)-1, data=request.data)], leader_commit=self.commit_index))

        except Exception as e:
            self.send_vote_request(IP_ADDRESS)

    def become_leader(self):
        self.current_state = "leader"
        print("I am now a leader")
        self.heartbeat_timer.restart_timer()

        # self.__election_timer__.cancel()
        # self.__heartbeat_timer__.cancel()
        # self.__heartbeat_timer__ = Timer(_HEARTBEAT_TIMEOUT__, self.send_heart_beats)

        for i in range(_NUMBER_OF_NODES_IN_CONSENSUS__):
            self.next_index.append(len(self.log))
            self.match_index.append(0)

        while self.current_state == "leader":
            # start sending periodic empty AppendEntries RPCs
            self.heartbeat_timer.countDown()
            self.send_heart_beats()

            # rsp = self.receive_append_entries_response()

            # if rsp != None and rsp.success == False:
            #     # if AppendEntries fails because of log inconsistency, decrement nextIndex and retry
            #     if rsp.term > self.current_term:
            #         self.current_term = rsp.term
            #         self.voted_for = None
            #         self.run_election_timer()
            #         return
            #     self.next_index[rsp.server_id] -= 1
            #     self.send_append_entries(rsp.server_id)
        self.run_election_timer()

    # def receive_append_entries_response(self):
    #     pass

    def send_heart_beats(self):
        print('Term: ', self.current_term)
        # leader send heartbeat messages to all the servers to establish authority

        # send initial empty AppendEntries RPCs
        for i in range(_NUMBER_OF_NODES_IN_CONSENSUS__):
            try:
                if (i == __ID__):
                    continue

                append_entries_rpc = AppendEntriesReq(
                    term=self.current_term,
                    leader_id=__ID__,
                    prev_log_index=self.next_index[i]-1,
                    prev_log_term=self.log[self.next_index[i]-1].term if self.next_index[i] > 0 else 0,
                    entries=self.log[self.next_index[i]:] if self.next_index[i] < len(self.log) else [],
                    leader_commit=self.commit_index)
                
                # IP address of the node
                IP_ADDRESS = _IP_ADDRESS_LIST[i]

                channel = grpc.insecure_channel(IP_ADDRESS)
                stub = raft_pb2_grpc.RaftStub(channel)

                stub.AppendEntries(append_entries_rpc)
                # start sending periodic empty AppendEntries RPCs
            except Exception as e:
                print(
                    f"Node {_IP_ADDRESS_LIST[i]} is busy or not available")
                # print(e)
                continue

    def run_election_timer(self):
        print("Node is now a follower")
        self.current_state = "follower"
        self.votes = 0

        # If node receives no communication from the leader, then it becomes a candidate and start election

        self.election_timeout.countDown()
        # timeouts are initialized to random values to prevent simultaneous elections

        # election timeout is reached, start election
        self.become_candidate()

    def become_candidate(self):
        print("I am now a candidate")

        # all the threads will be active
        self.stop_thread = False

        # candidate increments current term and transition to candidate state
        self.current_term += 1
        self.current_state = "candidate"

        # vote for itself
        self.votes = 1

        # vote for itself
        self.voted_for = __ID__

        # thread list
        threads = []
        # send vote requests to all other nodes
        for i in range(_NUMBER_OF_NODES_IN_CONSENSUS__):
            # if in between another node became the leader, stop the election
            if (self.current_state != "candidate"):
                self.stop_thread = True
                self.run_election_timer()
                break
            if (i == __ID__):
                continue

            # IP address of the node
            IP_ADDRESS = _IP_ADDRESS_LIST[i]
            print(f"Sending vote request to {IP_ADDRESS}")

            t = threading.Thread(
                target=self.send_vote_request, args=(IP_ADDRESS,))
            t.start()
            threads.append(t)
        candidate_timeout = CountDownTimer(MAX_T=_MAX_ELECTION_TIMEOUT__, type='fixed')
        candidate_timeout_thread = threading.Thread(
            target=candidate_timeout.countDown,args=())
        # try:
        #     candidate_timeout_thread.start()
        # except Exception as e:
        #     pass
        candidate_timeout_thread.start()
        while (self.current_state == "candidate" and candidate_timeout.Timer != 0 and self.stop_thread == False):
            # if majority of votes, become leader and run leader code

            if self.votes > _NUMBER_OF_NODES_IN_CONSENSUS__ / 2:

                print(f"Election won {self.current_term}")
                self.stop_thread = True
                self.become_leader()
                break
            elif (any(t.is_alive() for t in threads) == False):
                self.run_election_timer()
                break

        self.stop_thread = True
        self.run_election_timer()

    def send_vote_request(self, IP_ADDRESS):
        try:
            if (self.stop_thread == True):
                return
            channel = grpc.insecure_channel(IP_ADDRESS)
            stub = raft_pb2_grpc.RaftStub(channel)

            lst_lng_t = 0
            if (len(self.log) > 0):
                lst_lng_t = self.log[-1][1]

            response = stub.RequestVote(RequestVoteReq(term=self.current_term, candidate_id=__ID__, last_log_index=max(
                len(self.log)-1, -1), last_log_term=lst_lng_t))

            vote_granted = response.vote_granted
            term = response.term

            # if received the vote
            if (vote_granted == True):
                self.votes += 1
            else:
                if (term > self.current_term):
                    self.current_term = term
                    # as the term is updated and server has not voted in the updated term
                    self.voted_for = None
                    self.run_election_timer()
                    return
        except Exception as e:
            self.send_vote_request(IP_ADDRESS)


def serve():
    raft_node = Raft()
    _PORT_ = int(input("Enter port number: "))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    raft_pb2_grpc.add_RaftServicer_to_server(raft_node, server)
    print(f'localhost:{_PORT_}')
    server.add_insecure_port(f'localhost:{_PORT_}')
    server.start()

    try:
        raft_node.run_election_timer()
        # if (raft_node.current_state == "leader"):
        #     raft_node.become_leader()
        while True:
            time.sleep(86400)

    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    serve()
