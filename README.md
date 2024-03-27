# Raft Implementation in Python with Leader Lease
Raft is a consensus algorithm designed for distributed systems to ensure fault tolerance and consistency. This project aima to build a database that ensures fault tolerance and strong consistency. The client requests the server to perform operations on this database reliably. We use **gRPC** for communication between server nodes in the cluster.

## Leader Lease
In this implementation, we use the concept of leader leases to reduce the number of times the leader has to confirm its leadership. The leader lease is a time period during which no other node will attempt to become leader, thus reducing the number of elections.

## Dependencies
1. grpc
2. grpcio-tools
3. protobuf

Install by running: `pip install grpcio grpcio-tools protobuf`

## How to Run
1. `python node.py <node_id>` for each of the node {0, 1, 2}
2. `python client.py`


## Misc
### Compile Protocol Buffer
*Run in src directory*

`python -m grpc_tools.protoc -I../protos --python_out=. --pyi_out=. --grpc_python_out=. ../protos/raft.proto`

### Install gcloud CLI
1. `sudo apt-get install apt-transport-https ca-certificates gnupg curl sudo`

2. `curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-463.0.0-linux-x86_64.tar.gz`

3. `tar -xf google-cloud-cli-463.0.0-linux-x86_64.tar.gz`

4. `./google-cloud-sdk/install.sh`

5. `gcloud init`
   
6. `gcloud auth login`

### SSH to VM
VM 1: `gcloud compute ssh --zone "us-central1-b" "market-server-dscd" --project "dscd-assignment-1-414105"`

VM 2: `gcloud compute ssh --zone "us-central1-f" "seller-client-dscd" --project "dscd-assignment-1-414105"`

VM 3: `gcloud compute ssh --zone "us-central1-b" "buyer-client-dscd" --project "dscd-assignment-1-414105"`

### Transfer files to VM using scp
VM 1: `gcloud compute scp --recurse src market-server-dscd:~`

VM 2: `gcloud compute scp --recurse src seller-client-dscd:~`

VM 3: `gcloud compute scp --recurse src buyer-client-dscd:~`