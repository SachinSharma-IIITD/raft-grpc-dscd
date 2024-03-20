import grpc
from concurrent import futures
import time
from threading import Timer
import raft_pb2
from raft_pb2 import *
import raft_pb2_grpc
import sys
from timer import countDownTimer
import threading
import random

_MAX_ELECTION_TIMEOUT__ = 15
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


        self.election_timeout = countDownTimer()
        self.append_entries_timeout = countDownTimer()

        self.current_state = "follower" # keep the status of the server (follower, candidate, leader)
        self.votes = 0
        self.stop_thread = False
        self.heart_beat_received = 0 # track the number of heart beat responses received
        self.stop_heart_beat_thread = False # flag to stop the threads used to send the heart beat messages
        self.leader_lease_timeout = countDownTimer()

        # leader lease duration (to be propagated to the followers)
        self.leader_lease_time_acquired = 5

    def RequestVote(self, request, context):
        print("---------------------------------")
        print(f"{time.time()} Received vote request from {request.candidate_id} {request.term} {self.current_term} {self.voted_for}")
        print("---------------------------------")
        if request.term < self.current_term:
            return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=False)
        
        # in request received request from a node with a term greater than the current term, then update the current term
        elif request.term > self.current_term:
            self.current_term = request.term
            self.voted_for = None
            self.current_state = "follower"


        if self.voted_for is None or self.voted_for == request.candidate_id:
            # Check if candidate's log is at least as up-to-date as receiver's log
            if (len(self.log)==0 or self.log[-1].term < request.last_log_term) or (self.log[-1].term == request.last_log_term and len(self.log) <= request.last_log_index):
                self.voted_for = request.candidate_id
                print(f"{time.time()} vote granted")
                self.election_timeout.UpdateTimeout()
                return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=True,leader_lease = self.leader_lease_time_acquired)
        print(f"{time.time()} vote denied")
        return raft_pb2.RequestVoteResponse(term=self.current_term, vote_granted=False)


    def AppendEntries(self, request, context):

        if self.current_state == 'leader' and self.current_term >= request.term:
            return raft_pb2.AppendEntriesResponse(term=self.current_term, success=False)

        if (request.term > self.current_term):
            # if the server is in the candidate state, it will revert back to follower state
            self.current_state = "follower"
        
        self.election_timeout.UpdateTimeout()

        # this is not part of raft (for testing purpose only (over to sachin))
        if (request.entries == []):
            self.leader_lease_time_acquired = request.leader_lease
            return raft_pb2.AppendEntriesResponse(term=self.current_term, success=True)
        
    
        # if the term of the request is less than the current term, then reject the request
        if request.term < self.current_term:
            
            return raft_pb2.AppendEntriesResponse(term=self.current_term, success=False)
        else:
            self.current_term = request.term
            self.voted_for = None
        if len(self.log) == 0 and request.prev_log_index >= 0:
            return raft_pb2.AppendEntriesResponse(term=self.current_term, success=False)
        
        if len(self.log)>0 and  len(self.log) < request.prev_log_index + 1 or self.log[request.prev_log_index].term != request.prev_log_term:
            return raft_pb2.AppendEntriesResponse(term=self.current_term, success=False)
        else:
            self.log = self.log[:request.prev_log_index + 1]
        if (len(request.entries) > 0):
            self.log.extend(request.entries)
        
        if request.leader_commit > self.commit_index:
            self.commit_index = min(request.leader_commit, len(self.log) - 1)
        
        self.leader_lease_time_acquired = request.leader_lease
        return raft_pb2.AppendEntriesResponse(term=self.current_term, success=True)
    


    def Append(self, request, context):
        if self.current_state != "leader":
            return raft_pb2.ClientResponse(success=False)
        self.log.append((request.data, self.current_term))

        threads = []
        for i in range(_NUMBER_OF_NODES_IN_CONSENSUS__):
            try:
                if (i==__ID__):
                    continue
                # IP address of the node
                IP_ADDRESS = _IP_ADDRESS_LIST[i]

                t = threading.Thread(target=self.append_parallel, args=(IP_ADDRESS, request,))
                t.start()

            except Exception as e:
                print(f"{time.time()} Node {_IP_ADDRESS_LIST[i]} is busy or not available")
                continue

    def append_parallel(self, IP_ADDRESS, request):

        try:
            channel = grpc.insecure_channel(IP_ADDRESS)
            stub = raft_pb2_grpc.RaftStub(channel)

            lst_lng_t = 0
            if (len(self.log) > 0):
                lst_lng_t = self.log[-1][1]

            response = stub.AppendEntries(raft_pb2.AppendEntriesReq(term=self.current_term, leader_id=__ID__, prev_log_index = len(self.log)-2, prev_log_term = self.log[-2][1], entries = [raft_pb2.LogEntry(term=self.current_term, index=len(self.log)-1, data=request.data)], leader_commit = self.commit_index))   

                     
        except Exception as e:
            self.send_vote_request(IP_ADDRESS)
    
    def heart_beat_parallel(self, IP_ADDRESS):
        try:
            if (self.stop_heart_beat_thread == True):
                return
            channel = grpc.insecure_channel(IP_ADDRESS)
            stub = raft_pb2_grpc.RaftStub(channel)            

            # try:
            response = stub.AppendEntries(raft_pb2.AppendEntriesReq(
                term=self.current_term, 
                leader_id=__ID__, 
                prev_log_index = (-1 if len(self.log)==0 else len(self.log)-2), 
                prev_log_term = (0 if (len(self.log)==0) else self.log[-2][1]), 
                entries = [], 
                leader_commit = self.commit_index,
                leader_lease = self.leader_lease_time_acquired
            ))
            
            success = response.success
            term = response.term

            # if received the vote
            if (success == True):
                self.heart_beat_received += 1
            else:
                if (term > self.current_term):
                    self.current_term = term
                    # as the term is updated and server has not voted in the updated term
                    self.voted_for = None
                    self.current_state = "follower" 
                    return
        except Exception as e:
            self.heart_beat_parallel(IP_ADDRESS)
        

    
    def send_heart_beats(self):

        # before transitioning to leader, it need to wait till 
        new_leader_wait = countDownTimer()
        print(f"{time.time()} wait start as new leader: lease remaining = {self.leader_lease_time_acquired}")
        new_leader_wait.countDown(self.leader_lease_time_acquired)

        heart_beat_timer = countDownTimer() # this timer is responsible for sending heart beat messages to all the servers
        self.current_state = "leader" # making current state as leader
        print(f"{time.time()} I am now a leader")

        # this countdown is responsible for lease timeout of the leader
        
        leader_lease_timeout_thread = threading.Thread(target=self.leader_lease_timeout.countDown, args=(random.randint(5,10),))
        self.leader_lease_time_acquired = self.leader_lease_timeout.Timer
        leader_lease_timeout_thread.start()

        while self.current_state == "leader" and self.leader_lease_timeout.Timer != 0:
            heart_beat_timer.countDown(2)
            # leader send heartbeat messages to all the servers to establish authority after every 3 seconds

            # threads list
            threads = []

            self.heart_beat_received = 1

            # send initial empty AppendEntries RPCs
            for i in range(_NUMBER_OF_NODES_IN_CONSENSUS__):
                if (i==__ID__):
                    continue

                self.stop_heart_beat_thread = False
                # IP address of the node
                IP_ADDRESS = _IP_ADDRESS_LIST[i]
                # start sending periodic empty AppendEntries RPCs

                t = threading.Thread(target=self.heart_beat_parallel,args=(IP_ADDRESS,))
                t.start()
                threads.append(t)
                
            while(self.leader_lease_timeout.Timer != 0): 
                if (self.heart_beat_received > _NUMBER_OF_NODES_IN_CONSENSUS__ / 2):
                    self.stop_heart_beat_thread = True
                    self.leader_lease_timeout.UpdateTimeout()
                    print(f"{time.time()} A")
                    self.leader_lease_time_acquired = self.leader_lease_timeout.Timer
                    break
            
        self.stop_heart_beat_thread = True
        self.run_election_timer()
                    
    def run_election_timer(self):
        print(f"{time.time()} Node is now a follower")
        self.current_state = "follower"
        self.votes = 0

        # If node receives no communication from the leader, then it becomes a candidate and start election

        self.election_timeout.countDown(random.randint(5, 10))
        # timeouts are initialized to random values to prevent simultaneous elections

        # election timeout is reached, start election
        self.become_candidate()

    
    def become_candidate(self):
        print(f"{time.time()} I am now a candidate")

        # all the threads are active
        self.stop_thread = False

        candidate_timeout = countDownTimer()
        candidate_timeout_thread = threading.Thread(target=candidate_timeout.countDown, args=(random.randint(5, 10),))
        candidate_timeout_thread.start()


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
            if (i==__ID__):
                continue

            # IP address of the node
            IP_ADDRESS = _IP_ADDRESS_LIST[i]
            print(f"{time.time()} Sending vote request to {IP_ADDRESS}")

            t = threading.Thread(target=self.send_vote_request, args=(IP_ADDRESS,))
            t.start()
            threads.append(t)   
        
        
        while(self.current_state == "candidate" and candidate_timeout.Timer != 0 and self.stop_thread == False):
            # if majority of votes, become leader and run leader code
            
            if self.votes > _NUMBER_OF_NODES_IN_CONSENSUS__ / 2:
                
                print(f"{time.time()} Election won {self.current_term}")
                self.stop_thread = True
                # self.send_heart_beats()
                self.current_state = "leader"
                break
            elif (any(th.is_alive() for th in threads) == False):
                self.current_state = "follower"
                break
        
        if (self.current_state == "leader"):
            self.stop_thread = True
            candidate_timeout.Timer = 0
            self.send_heart_beats()
        else:
            self.stop_thread = True
            candidate_timeout.Timer = 0
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

            response = stub.RequestVote(raft_pb2.RequestVoteReq(term=self.current_term, candidate_id=__ID__, last_log_index = max(len(self.log)-1, -1) , last_log_term = lst_lng_t))
            
            vote_granted = response.vote_granted    
            term = response.term

            self.leader_lease_time_acquired = max(response.leader_lease,self.leader_lease_time_acquired)

            # if received the vote
            if (vote_granted == True):
                self.votes += 1
            else:
                if (term > self.current_term):
                    self.current_term = term
                    # as the term is updated and server has not voted in the updated term
                    self.voted_for = None
                    self.current_state = "follower"
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
        if (raft_node.current_state == "leader"):
            raft_node.send_heart_beats()
        while True:
            time.sleep(86400)

    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    serve()
