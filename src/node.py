import grpc
from concurrent import futures
import time
from raft_pb2 import RequestVoteReq, RequestVoteResponse, AppendEntriesReq, AppendEntriesResponse, LogEntry, GetReq, GetResponse, SetReq, SetResponse
import raft_pb2_grpc
import sys
from timer import CountDownTimer
import threading
import os

_MAX_ELECTION_TIMEOUT__ = 10
_HEARTBEAT_TIMEOUT__ = 3
_MAX_LEASE_TIMEOUT__ = 10
_NUMBER_OF_NODES_IN_CONSENSUS__ = 3
_IP_ADDRESS_LIST = ['127.0.0.1:8000', '127.0.0.1:8001', '127.0.0.1:8002']
__ID__ = int(sys.argv[1])


class Raft(raft_pb2_grpc.RaftServicer):
    def __init__(self):
        # Persistent state on all servers
        self.current_term = 0
        self.voted_for = -1
        self.log = []
        self.db = {}
        self.current_leader = -1  # stores the current leader

        # Volatile state on all servers
        self.commit_index = -1
        self.last_applied = 0

        self.data_dir_path = f'../data/logs_node_{__ID__}'
        self.log_path = self.data_dir_path + '/log.txt'
        self.metadata_path = self.data_dir_path + '/metadata.txt'

        if not os.path.exists(self.data_dir_path):
            os.makedirs(self.data_dir_path)

        if os.path.exists(self.log_path):
            with open(self.log_path, 'r') as f:
                index = 0
                for line in f.readlines():
                    entry = line.strip().split()
                    if entry[0] == 'SET':
                        self.log.append(
                            LogEntry(term=int(entry[2]), index=int(index), data=f'SET {entry[1]} {entry[2]}'))
                    else:
                        self.log.append(
                            LogEntry(term=int(entry[1]), index=int(index), data=entry[0]))
                    index += 1
                f.close()
        else:
            with open(self.log_path, 'w') as f:
                f.write('')
                f.close()

        if os.path.exists(self.metadata_path):
            with open(self.metadata_path, 'r') as f:
                data = f.read().strip().split()
                self.current_term = int(data[0])
                self.commit_index = int(data[1])
                self.voted_for = int(data[2])
                f.close()

        if self.commit_index > -1:
            for i in range(self.commit_index + 1):
                entry = self.log[i].data.split()
                if entry[0] == 'SET':
                    self.db[entry[1]] = entry[2]

        # Volatile state on leaders
        self.next_index = []
        self.match_index = []

        self.election_timeout = CountDownTimer(
            MAX_T=_MAX_ELECTION_TIMEOUT__, type='random')
        self.heartbeat_timer = CountDownTimer(
            MAX_T=_HEARTBEAT_TIMEOUT__, type='fixed')
        self.leader_lease_timeout = CountDownTimer(
            MAX_T=_MAX_LEASE_TIMEOUT__, type='fixed')

        # keep the status of the server (follower, candidate, leader)
        self.current_state = "follower"
        self.votes = 0
        self.stop_thread = False
        self.heart_beat_received = 0  # track the number of heart beat responses received
        # flag to stop the threads used to send the heart beat messages
        self.stop_heart_beat_thread = False

        # leader lease duration (to be propagated to the followers)
        self.leader_lease_time_acquired = 0

        # before transitioning to leader, it need to wait till
        self.follower_end_leader_lease = CountDownTimer(
            MAX_T=_MAX_LEASE_TIMEOUT__, type='fixed')
        self.follower_end_leader_lease.Timer = 0
        self.Is_follower_end_leader_lease_finished = True
        # print(f"{time.time()} wait start as new leader: lease remaining = {self.leader_lease_time_acquired}")
        self.leader_wait_thread = threading.Thread(
            target=self.leader_wait_thread_event)
        self.leader_wait_thread.start()

    def RequestVote(self, request, context):
        print("---------------------------------")
        print(f"{time.time()} Received vote request from {request.candidate_id} {request.term} {self.current_term} {self.voted_for}")
        print("---------------------------------")

        metadata_updated = False

        if request.term < self.current_term:
            return RequestVoteResponse(term=self.current_term, vote_granted=False, leader_lease=self.follower_end_leader_lease.Timer)

        # in request received request from a node with a term greater than the current term, then update the current term
        elif request.term > self.current_term:
            self.current_term = request.term
            self.voted_for = -1
            self.current_state = "follower"
            self.election_timeout.restart_timer()
            metadata_updated = True
            # this return need to be removed
            # print(f"{time.time()} vote granted")
            # return RequestVoteResponse(term=self.current_term, vote_granted=True)

        if self.voted_for == -1 or self.voted_for == request.candidate_id:
            # Check if candidate's log is at least as up-to-date as receiver's log
            if (len(self.log) == 0 or self.log[-1].term < request.last_log_term) or (self.log[-1].term == request.last_log_term and self.log[-1].index <= request.last_log_index):
                self.voted_for = request.candidate_id
                print(f"{time.time()} vote granted")
                self.election_timeout.restart_timer()
                print(
                    f'Leader lease time acquired: {self.leader_lease_time_acquired}')

                with open(self.metadata_path, 'w') as f:
                    f.write(
                        f"{self.current_term} {self.commit_index} {self.voted_for}")
                    f.close()

                return RequestVoteResponse(term=self.current_term, vote_granted=True, leader_lease=self.follower_end_leader_lease.Timer)

        print(f"{time.time()} vote denied")

        if metadata_updated:
            with open(self.metadata_path, 'w') as f:
                f.write(
                    f"{self.current_term} {self.commit_index} {self.voted_for}")
                f.close()

        return RequestVoteResponse(term=self.current_term, vote_granted=False, leader_lease = self.follower_end_leader_lease.Timer)

    def AppendEntries(self, request, context):
        print("---------------------------------")
        print(f"{time.time()} Received AppendEntries from {request.leader_id} {request.term} {self.current_term} {request.prev_log_term} {request.prev_log_index} {request.leader_commit}")
        print("---------------------------------")

        metadata_updated = False

        if (request.term > self.current_term):
            # if the server is in the candidate state, it will revert back to follower state
            self.current_state = "follower"
            self.current_term = request.term
            self.voted_for = -1
            metadata_updated = True

        if request.term == self.current_term:
            print('Cur log len: ', len(self.log))

            if (len(self.log) > request.prev_log_index):
                if not len(self.log) or (request.prev_log_index == -1 or self.log[request.prev_log_index].term == request.prev_log_term):
                    # Approve the request
                    self.log = self.log[:request.prev_log_index + 1]
                    self.log.extend(request.entries)

                    if len(request.entries) > 0:
                        metadata_updated = True
                        with open(self.log_path, 'w') as f:
                            for entry in self.log:
                                f.write(
                                    f"{entry.data} {entry.term}\n")
                            f.close()

                    if request.leader_commit > self.commit_index:
                        metadata_updated = True
                        new_commit_index = min(
                            request.leader_commit, len(self.log) - 1)

                        while self.commit_index < new_commit_index:
                            self.commit_index += 1
                            entry = self.log[self.commit_index].data.split()
                            if entry[0] == 'SET':
                                self.db[entry[1]] = entry[2]

                    print('Success AppendEntries')
                    if self.current_leader != request.leader_id:
                        metadata_updated = True
                    self.current_leader = request.leader_id
                    self.election_timeout.restart_timer()
                    self.leader_lease_time_acquired = request.leader_lease
                    self.follower_end_leader_lease.Timer = request.leader_lease
                    print(
                        f'{time.time()} Leader lease time acquired: {self.leader_lease_time_acquired} crnt_term = {self.current_term}')

                    print(f"Log: {self.log}")

                    if metadata_updated:
                        with open(self.metadata_path, 'w') as f:
                            f.write(
                                f"{self.current_term} {self.commit_index} {self.current_leader}")
                            f.close()
                    return AppendEntriesResponse(term=self.current_term, success=True)

        if metadata_updated:
            with open(self.metadata_path, 'w') as f:
                f.write(
                    f"{self.current_term} {self.commit_index} {self.voted_for}")
                f.close()
        return AppendEntriesResponse(term=self.current_term, success=False)

    def Set(self, request, context):
        print("---------------------------------")
        print(f"{time.time()} Received Set Req for {request.key} {request.value}")
        print("---------------------------------")

        if self.current_state != "leader":
            print(f"{time.time()} SET failed")
            return SetResponse(success=False, leader_id=self.current_leader)

        self.log.append(LogEntry(term=self.current_term, index=len(
            self.log), data=f'SET {request.key} {request.value}'))
                
        with open(self.log_path, 'a') as f:
            f.write(f"SET {request.key} {request.value} {self.current_term}\n")
            f.close()

        while self.commit_index != self.log[-1].index:
            time.sleep(1)

        print(f"{time.time()} SET success")
        return SetResponse(success=True, leader_id=__ID__)

    def Get(self, request, context):
        print("---------------------------------")
        print(f"{time.time()} Received Get Req for {request.key}")
        print("---------------------------------")

        if self.current_state == "leader" and self.leader_lease_timeout.Timer != 0:
            value = self.db.get(request.key, "")
            return GetResponse(success=True, value=value, leader_id=__ID__)
        else:
            return GetResponse(success=False, value="", leader_id=self.current_leader)

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
            self.heartbeat_timer.countDown(annotation='Heartbeat timer')
            self.send_heart_beats()

        self.run_election_timer()

    def heart_beat_parallel(self, IP_ADDRESS):
        try:
            if (self.stop_heart_beat_thread == True or self.leader_lease_timeout.Timer == 0 or self.current_state != "leader"):
                return
            channel = grpc.insecure_channel(IP_ADDRESS)
            stub = raft_pb2_grpc.RaftStub(channel)
            print(
                f"{self.leader_lease_time_acquired} lease time sending, cur_term = {self.current_term}")
            # try:
            i = _IP_ADDRESS_LIST.index(IP_ADDRESS)
            append_entries_rpc = AppendEntriesReq(
                term=self.current_term,
                leader_id=__ID__,
                prev_log_index=self.next_index[i]-1,
                prev_log_term=self.log[self.next_index[i] -
                                       1].term if self.next_index[i] > 0 else 0,
                entries=self.log[self.next_index[i]:] if self.next_index[i] < len(
                    self.log) else [],
                leader_commit=self.commit_index,
                leader_lease=self.leader_lease_time_acquired)

            response = stub.AppendEntries(append_entries_rpc)
            success_ = response.success
            term_ = response.term

            print(f"{time.time()} Heart beat response from {IP_ADDRESS} {success_} {term_} current_state : {self.current_state}")

            # if received the vote
            if (success_ == True):
                self.heart_beat_received += 1
                self.next_index[i] = len(self.log)
                self.match_index[i] = len(self.log) - 1
            else:
                if (term_ > self.current_term):
                    self.current_term = term_
                    # as the term is updated and server has not voted in the updated term
                    self.voted_for = -1
                    self.current_state = "follower"
                    with open(self.metadata_path, 'w') as f:
                        f.write(
                            f"{self.current_term} {self.commit_index} {self.voted_for}")
                        f.close()
                    return
                else:
                    self.next_index[i] -= 1
                    if (self.next_index[i] < 0):
                        self.next_index[i] = 0
        except Exception as e:
            # self.heart_beat_parallel(IP_ADDRESS)
            return

    def send_heart_beats(self):
        if self.current_state != 'leader':
            self.leader_lease_timeout.Timer = 0 
            self.stop_heart_beat_thread = True
            self.run_election_timer()
            return

        print(f"{time.time()} I am now a leader: term = {self.current_term} {self.leader_lease_time_acquired} lease time")

        # self.current_state = "leader"  # making current state as leader
        self.current_leader = __ID__  # making current leader as the node id

        metadata_updated = False

        # this countdown is responsible for lease timeout of the leader
        leader_lease_timeout_thread = threading.Thread(
            target=self.leader_lease_timeout.countDown, kwargs={'annotation': "leader lease timer"})
        leader_lease_timeout_thread.start()
        print(f'Leader lease time acquired: {self.leader_lease_time_acquired}')

        if self.current_state != 'leader':
            self.leader_lease_timeout.Timer = 0 
            self.stop_heart_beat_thread = True
            self.run_election_timer()
            return

        # print("timer : ",self.leader_lease_timeout.Timer)
        self.leader_lease_time_acquired = self.leader_lease_timeout.Timer
        for i in range(_NUMBER_OF_NODES_IN_CONSENSUS__):
            self.next_index.append(len(self.log))
            self.match_index.append(0)

        while ((self.current_state == "leader") and (self.leader_lease_timeout.Timer) != 0):
            self.heartbeat_timer.countDown(annotation='Heartbeat timer')
            # leader send heartbeat messages to all the servers to establish authority after every 3 seconds

            # threads list
            threads = []

            self.heart_beat_received = 1

            self.stop_heart_beat_thread = False

            # send initial empty AppendEntries RPCs
            for i in range(_NUMBER_OF_NODES_IN_CONSENSUS__):
                if (i == __ID__):
                    continue

                # IP address of the node
                IP_ADDRESS = _IP_ADDRESS_LIST[i]
                # start sending periodic empty AppendEntries RPCs

                t = threading.Thread(
                    target=self.heart_beat_parallel, args=(IP_ADDRESS,))
                t.start()
                threads.append(t)

            time.sleep(1)  # sleep for 1 second before checking any response
            if self.current_state != "leader":
                break

            if (self.heart_beat_received > _NUMBER_OF_NODES_IN_CONSENSUS__ / 2):
                new_commit_index = max(len(self.log)-1, self.commit_index)

                if new_commit_index > self.commit_index:
                    self.commit_index = new_commit_index
                    metadata_updated = True

                if self.commit_index > -1:
                    entry = self.log[self.commit_index].data.split()
                    if entry[0] == "SET":
                        self.db[entry[1]] = entry[2]

                self.stop_heart_beat_thread = True
                self.leader_lease_timeout.restart_timer()
                print(f"{time.time()} majority heart beat received")
                self.leader_lease_time_acquired = self.leader_lease_timeout.Timer

                if metadata_updated:
                    with open(self.metadata_path, 'w') as f:
                        f.write(
                            f"{self.current_term} {self.commit_index} {self.voted_for}")
                        f.close()
            else:
                continue

        self.leader_lease_timeout.Timer = 0 
        self.stop_heart_beat_thread = True
        self.run_election_timer()
        return

    def leader_wait_thread_event(self):

        # initially the leader lease time at follower is 0, for all the node
        while (self.follower_end_leader_lease.Timer == 0):
            pass

        self.Is_follower_end_leader_lease_finished = False
        # a new leader is elected, updated the follower end leader lease time, and here we have started its countdown timer
        self.follower_end_leader_lease.countDown(
            timeout=self.follower_end_leader_lease.Timer, annotation="follower end leader lease")

        self.Is_follower_end_leader_lease_finished = True

        self.leader_wait_thread_event()

    def run_election_timer(self):
        print(f"{time.time()} Node is now a follower: Term = {self.current_term}")
        self.current_state = "follower"
        self.votes = 0
        self.voted_for = -1
        self.stop_thread = False
        with open(self.metadata_path, 'w') as f:
            f.write(f"{self.current_term} {self.commit_index} {self.voted_for}")
            f.close()

        self.election_timeout.countDown(annotation="election timer")
        # timeouts are initialized to random values to prevent simultaneous elections

        # election timeout is reached, start election
        self.become_candidate()

    def become_candidate(self):
        print(f"{time.time()} I am now a candidate")

        # all the threads are active
        self.stop_thread = False

        candidate_timeout = CountDownTimer(
            MAX_T=_MAX_ELECTION_TIMEOUT__, type='random')
        candidate_timeout_thread = threading.Thread(
            target=candidate_timeout.countDown, kwargs={'annotation': 'candidate timer'})
        candidate_timeout_thread.start()

        # candidate increments current term and transition to candidate state
        self.current_term += 1
        self.current_state = "candidate"

        # vote for itself
        self.votes = 1

        # vote for itself
        self.voted_for = __ID__

        with open(self.metadata_path, 'w') as f:
            f.write(f"{self.current_term} {self.commit_index} {self.voted_for}")
            f.close()

        # thread list
        threads = []
        self.leader_lease_time_acquired = 0

        # send vote requests to all other nodes
        for i in range(_NUMBER_OF_NODES_IN_CONSENSUS__):
            # if in between another node became the leader, stop the election
            if (self.current_state != "candidate"):
                self.stop_thread = True
                print(f"{time.time()} No more candidate {self.current_term}")
                self.run_election_timer()
                break
            if (i == __ID__):
                continue

            # IP address of the node
            IP_ADDRESS = _IP_ADDRESS_LIST[i]
            print(f"{time.time()} Sending vote request to {IP_ADDRESS}")

            t = threading.Thread(
                target=self.send_vote_request, args=(IP_ADDRESS,))
            t.start()
            threads.append(t)

        while (self.current_state == "candidate" and candidate_timeout.Timer != 0 and self.stop_thread == False):
            # if majority of votes, become leader and run leader code

            if self.votes > _NUMBER_OF_NODES_IN_CONSENSUS__ / 2:

                print(f"{time.time()} Election won {self.current_term}")
                self.stop_thread = True
                # self.send_heart_beats()
                self.current_state = "leader"
                break

        candidate_timeout.Timer = 0
        self.stop_thread = True

        if (self.current_state == "leader"):
            if (self.follower_end_leader_lease.Timer >= self.leader_lease_time_acquired):
                while (self.Is_follower_end_leader_lease_finished == False):
                    print(
                        f"{time.time()} waiting for follower end leader lease {self.follower_end_leader_lease.Timer}")
            else:
                CountDownTimer(MAX_T=self.leader_lease_time_acquired, type='fixed').countDown(annotation="leader lease time")
            self.send_heart_beats()
        else:
            print(f"{time.time()} Election lost {self.current_term}")
            self.run_election_timer()

    def send_vote_request(self, IP_ADDRESS):
        try:
            if (self.stop_thread == True):
                return
            channel = grpc.insecure_channel(IP_ADDRESS)
            stub = raft_pb2_grpc.RaftStub(channel)

            lst_lng_t = 0
            if (len(self.log) > 0):
                lst_lng_t = self.log[-1].term

            response = stub.RequestVote(RequestVoteReq(
                term=self.current_term, candidate_id=__ID__, last_log_index=max(len(self.log)-1, -1), last_log_term=lst_lng_t))

            vote_granted_ = response.vote_granted
            term_ = response.term

            self.leader_lease_time_acquired = max(
                response.leader_lease, self.leader_lease_time_acquired)
            print(
                f'Leader lease time acquired: {self.leader_lease_time_acquired}')

            # if received the vote
            if (vote_granted_ == True):
                self.votes += 1
                print(f"{time.time()} vote received from {IP_ADDRESS}")
            else:
                if (term_ > self.current_term):
                    self.current_term = term_
                    # as the term is updated and server has not voted in the updated term
                    self.voted_for = -1
                    self.current_state = "follower"
                    with open(self.metadata_path, 'w') as f:
                        f.write(
                            f"{self.current_term} {self.commit_index} {self.voted_for}")
                        f.close()
                    return
        except Exception as e:
            # self.send_vote_request(IP_ADDRESS)
            return


def serve():
    print("process ID : ", os.getpid())
    raft_node = Raft()
    _PORT_ = int(input("Enter port number: "))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=100))
    raft_pb2_grpc.add_RaftServicer_to_server(raft_node, server)
    print(f'localhost:{_PORT_}')
    server.add_insecure_port(f'localhost:{_PORT_}')
    server.start()

    try:
        raft_node.run_election_timer()
        while True:
            time.sleep(86400)

    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    serve()
