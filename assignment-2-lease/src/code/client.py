import grpc
import raft_pb2
import raft_pb2_grpc

def run(Leader_IP):
    # Assuming the server is running on localhost at port 50051
    with grpc.insecure_channel('') as channel:
        stub = raft_pb2_grpc.RaftStub(channel)

        success = stub.Append(raft_pb2.LogEntry(term=1, index=1, data="Hello World!"))

        print(success.success)

if __name__ == '__main__':
    Leader_IP = input("Enter the IP address of the leader: ")
    run(Leader_IP)