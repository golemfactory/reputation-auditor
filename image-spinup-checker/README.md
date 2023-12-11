
# Important note
The script is not working as intended right now. The goal would be to run tasks on all providers and check if they can spin-up an image, but the whitelisting doesn't appear to be working as intended right now thus resulting in tasks not starting up. The script will write the provider failed, but that's not true since we never ever struck an agreement with them in the first place.

# Introduction

The script's primary function is to check if a node can successfully spin up a specified image. This capability is crucial for the reputation system within the Golem Network, as it helps in identifying faulty providers and estimating their theoretical download speed.

## Configuration

The script can be configured using command line arguments as detailed in the table below:

| Argument    | Description                                   | Default Value          |
| ----------- | --------------------------------------------- | ---------------------- |
| packageName | Name of the image to be spun up on the node.  | golem/alpine:latest    |
| nodeId      | Optional. Id to be whitelisted.               | null (random provider) |
| timeout     | Time limit for spinning up the image (in ms). | 60000 (1 minute)       |

### Script Execution Flow

The script initializes a task executor and listens for specific events such as `AgreementConfirmed` and `ActivityStateChanged`.
It attempts to spin up the specified image within the provided timeout period.
Success or failure of the task is logged, providing insights into the node's capabilities.
