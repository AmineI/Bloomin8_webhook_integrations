These files can be used by moving them to the root of the project. Deploying this on a local machine is needed to wake the device over bluetooth, which makes the azure function only usable in local deployment. 
The host.json file has been customized to avoid logging the warnings about azure storage being unavailable.
The Azure Functions runtime & Docker images are not available in many architectures such as ARM (Raspberry Pi, Macs, ...)
This approach will not be pursued further for now, and will likely be removed.