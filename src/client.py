import grpc
import raft_pb2
from raft_pb2 import GetReq, GetResponse, SetReq, SetResponse, LogEntry
import raft_pb2_grpc

Nodes = ['127.0.0.1:8000', '127.0.0.1:8001', '127.0.0.1:8002']
current_leader_index = 0

def send_request(request_func):
    global current_leader_index
    attempts = 0
    while attempts < len(Nodes):
        try:
            with grpc.insecure_channel(Nodes[current_leader_index]) as channel:
                stub = raft_pb2_grpc.RaftStub(channel)
                response = request_func(stub)
                if response.success:
                    print("Request successful")
                    return response.value if hasattr(response, 'value') else "Success"
                else:
                    if 0 <= response.leader_id < len(Nodes):
                        current_leader_index = response.leader_id
                        print(f"Updated leader to node at index {current_leader_index}. Retrying...")
                        attempts += 1
                        continue
                    else:
                        print("Received invalid leader_id. Retrying with next node...")
        except grpc.RpcError as e:
            print(f"Error contacting node {Nodes[current_leader_index]}: {e}")
        current_leader_index = (current_leader_index + 1) % len(Nodes)
        attempts += 1

    print("All nodes have been tried. Operation failed.")
    return "Operation failed."

def get(key):
    def request(stub):
        return stub.Get(GetReq(key=key))
    print(f"Getting value for key: {key}")
    return send_request(request)

def set(key, value):
    def request(stub):
        return stub.Set(SetReq(key=key, value=value))
    print(f"Setting value for key: {key} to {value}")
    return send_request(request)

def main():
    while True:
        print("\n1. Get a value by key")
        print("2. Set a value by key")
        print("3. Exit")
        choice = input("Enter choice: ")
        if choice == '1':
            key = input("Enter key: ")
            value = get(key)
            print(f"Value: {value}")
        elif choice == '2':
            key = input("Enter key: ")
            value = input("Enter value: ")
            response = set(key, value)
            print(response)
        elif choice == '3':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == '__main__':
    main()