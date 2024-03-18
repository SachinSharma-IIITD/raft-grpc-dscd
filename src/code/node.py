import grpc
from concurrent import futures
import time
from threading import Timer
from raft_pb2 import *
import raft_pb2_grpc


def run(node_sockets, ip, port):
    node_stubs = []
    try:
        # Create a gRPC channel to connect to other nodes
        for server_addr in node_sockets:
            channel = grpc.insecure_channel(server_addr)
            node_stubs.append(raft_pb2_grpc.RaftStub(channel))
            # stub.checkConnection(PingReq(message="Connection Request from Seller"))
    except:
        print('\nServer offline\n')
        exit(1)

    print('\nConnected to Raft cluster\n')

    # ops = ('Register Seller', 'Sell Product', 'Update Product', 'Delete Product',
    #        "Show Seller's Products", 'Exit')
    # ops = [f'{i+1}. {op}' for i, op in enumerate(ops)]


def set_election_timeout(election_timeout):
    Timer(election_timeout, become_candidate).start()
    print('Election Timeout')


def become_candidate():
    pass


class RaftNode(raft_pb2_grpc.RaftServicer):
    def __init__(self):
        self.current_term = 0
        self.voted_for = None
        self.log = []

    def RequestVote(self, request, context):
        if request.term < self.current_term:
            return RequestVoteResponse(term=self.current_term, vote_granted=False)
        elif request.term > self.current_term:
            self.current_term = request.term
            self.voted_for = None

        if self.voted_for is None or self.voted_for == request.candidate_id:
            # Check if candidate's log is at least as up-to-date as receiver's log
            if self.log[-1].term < request.last_log_term or (self.log[-1].term == request.last_log_term and len(self.log) <= request.last_log_index):
                self.voted_for = request.candidate_id
                return RequestVoteResponse(term=self.current_term, vote_granted=True)

        return RequestVoteResponse(term=self.current_term, vote_granted=False)

    def AppendEntries(self, request, context):
        if request.term < self.current_term:
            return AppendEntriesResponse(term=self.current_term, success=False)
        else:
            self.current_term = request.term
            self.voted_for = None
        if len(self.log) < request.prev_log_index + 1 or self.log[request.prev_log_index].term != request.prev_log_term:
            return AppendEntriesResponse(term=self.current_term, success=False)
        else:
            self.log = self.log[:request.prev_log_index + 1]
        self.log.extend(request.entries)
        if request.leader_commit > self.commit_index:
            self.commit_index = min(request.leader_commit, len(self.log) - 1)
        return AppendEntriesResponse(term=self.current_term, success=True)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    raft_pb2_grpc.add_RaftServicer_to_server(RaftNode(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    serve()
