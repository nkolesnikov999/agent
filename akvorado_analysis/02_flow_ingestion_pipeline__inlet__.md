# Chapter 2: Flow Ingestion Pipeline (Inlet)

In the [previous chapter](01_data_schema_.md), we learned about the `FlowMessage` and the Data Schema – Akvorado's blueprint for understanding network flow data. But how does that data actually get *into* Akvorado from your network devices in the first place? That's where the **Flow Ingestion Pipeline (Inlet)** comes in!

Think back to our LEGO® analogy. The Data Schema was the plan for our LEGO® bricks. Now, imagine a busy loading dock at the LEGO® factory. Trucks arrive carrying big boxes of mixed-up raw plastic pellets (raw flow data). The Inlet pipeline is like the team working at this loading dock. Their job is:

1.  **Receive Shipments:** Accept the trucks arriving at specific docks (listen on network ports like UDP).
2.  **Unpack Boxes:** Open the boxes and understand what's inside (decode the raw binary flow data like NetFlow v9, IPFIX, or sFlow).
3.  **Sort Items:** Organize the plastic pellets into the standard LEGO® brick shapes defined by the plan (transform the data into the structured `FlowMessage` format).
4.  **Manage Traffic:** Ensure the loading dock doesn't get overwhelmed if too many trucks arrive from the same supplier at once (apply rate limiting per network device).

The Inlet pipeline is the **entry point** for all network flow data into Akvorado.

## What Does the Inlet Pipeline Do?

The Inlet's main responsibilities are:

1.  **Listening for Data:** It opens specific "ears" to listen for incoming flow data. These are typically UDP ports on your server where your routers and switches (called "exporters") are configured to send their flow packets. It can also read data from files, which is useful for testing or replaying captured traffic.
2.  **Decoding Data:** Raw flow data arrives in compact binary formats like NetFlow v9, IPFIX, or sFlow. These are like different languages spoken by the network devices. The Inlet uses specific "translators" (decoders) for each format to understand the binary stream and extract meaningful information (IP addresses, ports, byte counts, etc.).
3.  **Structuring Data:** Once decoded, the information is organized into the standard `FlowMessage` format we learned about in Chapter 1. This ensures all data, regardless of its original format (NetFlow, sFlow, etc.), looks the same internally.
4.  **Rate Limiting:** Network devices can sometimes send *a lot* of flow data, potentially overwhelming Akvorado. The Inlet can limit the rate of flows processed from each individual device (exporter) to prevent this. If a device exceeds its limit, some of its data might be temporarily dropped, but Akvorado keeps track of this.

## Key Concepts

Let's break down the Inlet pipeline's parts:

### 1. Inputs: Where the Data Arrives

Inputs define *how* Akvorado receives the raw data. The most common input is **UDP**.

*   **UDP Input:** Listens on a specific UDP port (e.g., port 2055 for NetFlow, 6343 for sFlow). Your network devices must be configured to send their flow packets to the IP address of your Akvorado server and this specific port.
*   **File Input:** Reads flow data directly from files on the server. This is less common for live traffic but very useful for development, testing, or analyzing pre-captured data.

You configure inputs in your Akvorado configuration file. Here's a conceptual example of setting up two UDP inputs, one for NetFlow and one for sFlow:

```yaml
# Example Akvorado Configuration Snippet (Conceptual)
inlet:
  flow:
    inputs:
      - decoder: netflow # Use the NetFlow decoder for this input
        config:
          # UDP Input Specific Configuration
          type: udp
          listen: 0.0.0.0:2055 # Listen on port 2055 on all network interfaces
          workers: 2         # Use 2 parallel processes to handle incoming UDP packets
          receive_buffer: 8388608 # Set OS receive buffer size (optional)

      - decoder: sflow   # Use the sFlow decoder for this input
        config:
          # UDP Input Specific Configuration
          type: udp
          listen: 0.0.0.0:6343 # Listen on port 6343 on all network interfaces
          workers: 1
```

This tells Akvorado to start two listeners: one on UDP port 2055 expecting NetFlow data, and another on UDP port 6343 expecting sFlow data.

*(See `inlet/flow/config.go`, `inlet/flow/input/udp/root.go`, `inlet/flow/input/file/root.go` for related code)*

### 2. Decoders: Understanding the Data Format

Once an Input receives a packet (like a UDP datagram), the data inside is just a sequence of bytes. The **Decoder** is responsible for interpreting these bytes according to a specific flow protocol standard (NetFlow v9, IPFIX, sFlow, etc.).

*   **NetFlow/IPFIX Decoder:** Understands Cisco's NetFlow (especially v9) and the IETF standard IPFIX. These protocols use templates to define the structure of the flow records being sent. The decoder needs to receive and store these templates first before it can understand the actual data records.
*   **sFlow Decoder:** Understands the sFlow protocol (commonly version 5). sFlow sends sampled packet headers and counters, which the decoder parses.

Each Input you configure must be associated with a specific Decoder, as shown in the YAML example above (`decoder: netflow` or `decoder: sflow`). Akvorado knows which "translator" to use for the data arriving at that specific input.

*(See `inlet/flow/decoder.go`, `inlet/flow/decoder/netflow/root.go`, `inlet/flow/decoder/sflow/root.go` for related code)*

### 3. Output: The Structured `FlowMessage`

After the Decoder successfully parses the raw data, it creates one or more `FlowMessage` objects. As we learned in [Chapter 1](01_data_schema_.md), the `FlowMessage` is the standardized internal representation of a flow record within Akvorado, defined by the Data Schema.

Every `FlowMessage` produced by the Inlet contains the core flow information (like source/destination IPs and ports, byte/packet counts) plus metadata added by the Inlet itself, such as:

*   `TimeReceived`: When Akvorado received the flow packet.
*   `ExporterAddress`: The IP address of the network device that sent the data.

These structured `FlowMessage` objects are then passed on to the next stage of processing.

### 4. Rate Limiting: Preventing Overload

Imagine one of your routers suddenly starts sending 10 times more flow data than usual. This could overwhelm Akvorado's processing capacity or fill up storage quickly. The Inlet pipeline includes a **rate limiter** that acts like a traffic controller for each sending device (exporter).

*   You can configure a maximum number of flows per second allowed *per exporter*.
*   If an exporter exceeds this limit, the Inlet will start dropping *some* of its incoming flows.
*   Importantly, when flows are dropped due to rate limiting, Akvorado tries to adjust the `SamplingRate` field on the flows that *are* allowed through. This adjustment helps keep the traffic statistics (like total bytes) approximately correct, even though some individual flow records were missed.

This mechanism protects Akvorado from sudden floods of data from misbehaving or heavily loaded devices.

```go
// File: inlet/flow/rate.go (Simplified Concept)

// allowMessages checks if flows from an exporter are within the rate limit.
func (c *Component) allowMessages(fmsgs []*schema.FlowMessage) bool {
	// If rate limiting is disabled or no messages, allow passage.
	if c.config.RateLimit == 0 || len(fmsgs) == 0 {
		return true
	}

	exporter := fmsgs[0].ExporterAddress // Get the sender's IP
	exporterLimiter := c.getLimiterForExporter(exporter) // Find or create its specific rate limiter

	now := time.Now()
	// Check if the limiter allows this batch of messages
	if !exporterLimiter.l.AllowN(now, len(fmsgs)) {
		exporterLimiter.recordDrop(len(fmsgs)) // Record that flows were dropped
		c.metrics.RateLimitDrops.Inc() // Increment drop counter
		return false // Block these messages
	}

	// If allowed, potentially adjust sampling rate based on recent drops
	exporterLimiter.adjustSamplingRateIfNeeded(fmsgs)
	return true // Allow these messages
}
```

This conceptual code shows how the Inlet checks incoming `FlowMessage` batches against a per-exporter rate limiter. If the limit is exceeded (`AllowN` returns false), the flows are dropped.

*(See `inlet/flow/rate.go` for related code)*

## How it Works: The Journey of a Flow Packet

Let's trace the path of a single NetFlow packet sent from your router to Akvorado:

```mermaid

sequenceDiagram
    participant Router as Network Device (Exporter)
    participant UDPInput as Inlet UDP Input (e.g., port 2055)
    participant NetFlowDecoder as Inlet NetFlow Decoder
    participant RateLimiter as Inlet Rate Limiter
    participant OutputChannel as Inlet Output Channel

    Router->>+UDPInput: 1. Sends UDP Packet (Raw NetFlow data)
    UDPInput->>+NetFlowDecoder: 2. Receives bytes, passes to configured decoder
    NetFlowDecoder-->>-UDPInput: 3. Decodes bytes into FlowMessage(s)  # Деактивируем NetFlowDecoder
    UDPInput->>RateLimiter: 4. Passes FlowMessage(s) for rate check   # Убрали '+' активации
    alt Exporter within limit
        RateLimiter-->>UDPInput: 5a. Approves FlowMessage(s) (maybe adjusts sampling rate) # Убрали '-' деактивации
        UDPInput->>+OutputChannel: 6a. Sends FlowMessage(s) onward
        OutputChannel-->>-UDPInput: (Ready for next stage) # Деактивируем OutputChannel
    else Exporter exceeds limit
        RateLimiter-->>UDPInput: 5b. Rejects FlowMessage(s) # Убрали '-' деактивации
        UDPInput->>UDPInput: 6b. Drops FlowMessage(s) # Сообщение самому себе, UDPInput остается активным
    end

<!-- sequenceDiagram
    participant Router as Network Device (Exporter)
    participant UDPInput as Inlet UDP Input (e.g., port 2055)
    participant NetFlowDecoder as Inlet NetFlow Decoder
    participant RateLimiter as Inlet Rate Limiter
    participant OutputChannel as Inlet Output Channel

    Router->>+UDPInput: 1. Sends UDP Packet (Raw NetFlow data)
    UDPInput->>+NetFlowDecoder: 2. Receives bytes, passes to configured decoder
    NetFlowDecoder->>-UDPInput: 3. Decodes bytes into FlowMessage(s)
    UDPInput->>+RateLimiter: 4. Passes FlowMessage(s) for rate check
    alt Exporter within limit
        RateLimiter->>-UDPInput: 5a. Approves FlowMessage(s) (maybe adjusts sampling rate)
        UDPInput->>+OutputChannel: 6a. Sends FlowMessage(s) onward
        OutputChannel-->>-UDPInput: (Ready for next stage)
    else Exporter exceeds limit
        RateLimiter->>-UDPInput: 5b. Rejects FlowMessage(s)
        UDPInput->>UDPInput: 6b. Drops FlowMessage(s)
    end -->

```

1.  **Send:** Your router sends a UDP packet containing raw NetFlow data to Akvorado's IP address and the configured port (e.g., 2055).
2.  **Receive & Pass:** The Akvorado Inlet's UDP Input worker listening on port 2055 receives the packet bytes. It knows (from configuration) that this input uses the NetFlow Decoder, so it passes the raw bytes and the sender's IP address to the decoder.
3.  **Decode:** The NetFlow Decoder interprets the bytes. If it's data, it uses previously received templates to parse the fields. It creates one or more `FlowMessage` objects containing the structured flow data.
4.  **Rate Check:** The `FlowMessage` objects (which include the `ExporterAddress`) are passed to the Rate Limiter.
5.  **Limit Decision:** The Rate Limiter checks if this specific exporter is still within its allowed flows/second limit.
6.  **Forward or Drop:**
    *   **If Allowed (5a, 6a):** The `FlowMessage`(s) are approved (potentially with an adjusted `SamplingRate`) and placed onto the Inlet's output channel, ready for the next processing stage ([Core Processing Pipeline (Inlet)](03_core_processing_pipeline__inlet__.md)).
    *   **If Rejected (5b, 6b):** The `FlowMessage`(s) are dropped, and a metric is incremented to track the drops.

## Inside the Inlet Code

The main logic orchestrating the inputs and decoders lives within the `inlet/flow` package.

```go
// File: inlet/flow/root.go (Simplified Startup)

// New creates a new flow component.
func New(r *reporter.Reporter, config Configuration, deps Dependencies) (*Component, error) {
	c := Component{
		// ... initialization ...
		outgoingFlows: make(chan *schema.FlowMessage), // Channel to send processed flows out
		limiters:      make(map[netip.Addr]*limiter),  // Map to hold per-exporter rate limiters
		inputs:        make([]input.Input, len(config.Inputs)),
		// ... metrics setup ...
	}

	// Initialize configured decoders (e.g., NetFlow, sFlow)
	decs := c.initializeDecoders(config.Inputs)

	// Initialize configured inputs (e.g., UDP listeners)
	for idx, inputConfig := range config.Inputs {
		// inputConfig.Config holds specific config like UDP port, file path
		// decs[idx] is the specific decoder instance for this input
		c.inputs[idx], err = inputConfig.Config.New(r, deps.Daemon, decs[idx])
		// ... error handling ...
	}
	// ... more setup ...
	return &c, nil
}

// Start begins processing for all configured inputs.
func (c *Component) Start() error {
	for _, input := range c.inputs { // Iterate through configured inputs (UDP, File...)
		inputChannel, err := input.Start() // Tell the input to start listening/reading
		// ... error handling ...

		// Start a goroutine (concurrent process) to handle flows from this specific input
		c.t.Go(func() error {
			// Loop forever, reading from the input's channel
			for flowMessagesFromInput := range inputChannel {
				// Check rate limit for this batch of flows
				if c.allowMessages(flowMessagesFromInput) {
					// If allowed, send each flow message to the main outgoing channel
					for _, fmsg := range flowMessagesFromInput {
						select {
						case c.outgoingFlows <- fmsg: // Send to next stage
						// ... handle shutdown signal ...
						}
					}
				} else {
					// Rate limited: flows are dropped here (logged inside allowMessages)
				}
			}
			return nil
		})
	}
	return nil
}
```

1.  `New`: Sets up the component, creates the output channel (`outgoingFlows`), initializes the map for rate limiters, and critically, loops through the `config.Inputs` section of your configuration. For each input, it creates the corresponding `Decoder` and `Input` instances (like `udp.Input` or `file.Input`).
2.  `Start`: Iterates through the created `Input` objects. For each one, it calls `input.Start()`, which returns a channel (`inputChannel`) where that specific input will send the `FlowMessage` objects it produces. A separate lightweight process (goroutine) is started for each input channel. This process reads batches of `FlowMessage`s, checks them against the `allowMessages` rate limiter function, and if allowed, sends them one-by-one to the central `c.outgoingFlows` channel.

The UDP input itself handles the low-level network listening:

```go
// File: inlet/flow/input/udp/root.go (Simplified UDP Read Loop)

// Start starts listening to the provided UDP socket
func (in *Input) Start() (<-chan []*schema.FlowMessage, error) {
	// ... setup UDP connection(s) ...
	conn := connectToUDPPort(in.config.Listen) // Simplified connection setup

	// Start a worker goroutine to read from the UDP socket
	in.t.Go(func() error {
		payload := make([]byte, 9000) // Buffer for incoming UDP data
		for { // Loop forever reading packets
			// Read data from the UDP connection
			numBytes, senderAddress, err := conn.ReadFromUDP(payload)
			// ... error handling (check for closed connection, log errors) ...

			// Get receive timestamp (important!)
			receivedTime := time.Now() // Or use kernel timestamp if available

			// Pass the raw bytes and sender IP to the configured decoder
			flows := in.decoder.Decode(decoder.RawFlow{
				TimeReceived: receivedTime,
				Payload:      payload[:numBytes], // Only the received bytes
				Source:       senderAddress.IP,
			})

			// If decoder produced messages, send them to the output channel
			if len(flows) > 0 {
				select {
				case in.ch <- flows: // Send the batch of FlowMessages
				// ... handle queue full (drop) or shutdown ...
				}
			}
		}
	})
	return in.ch, nil // Return the channel where FlowMessages will appear
}
```

This shows the core loop of a UDP input worker: read a packet, get the raw bytes and sender IP, call the `decoder.Decode` method (which uses the specific NetFlow/sFlow decoder instance configured for this input), and if successful, send the resulting `FlowMessage` slice onto its output channel (`in.ch`). This channel is the one read by the main `Start` loop in `inlet/flow/root.go`.

## Conclusion

The Flow Ingestion Pipeline (Inlet) is Akvorado's crucial first step in processing network data. It acts as the "front door" and "unpacking station":

*   It **listens** for raw flow data using configured Inputs (like UDP sockets).
*   It **decodes** the various binary formats (NetFlow, sFlow, IPFIX) into understandable information using Decoders.
*   It **structures** this information into the standard `FlowMessage` format defined by the [Data Schema](01_data_schema_.md).
*   It **protects** the system from being overwhelmed using per-exporter Rate Limiting.

The output of this pipeline is a steady stream of structured `FlowMessage` objects, ready for further enrichment and processing.

Now that we know how data gets *into* Akvorado and is initially structured, let's see what happens next in the main processing stage.

Next up: [Chapter 3: Core Processing Pipeline (Inlet)](03_core_processing_pipeline__inlet__.md)

---

Generated by [AI Codebase Knowledge Builder](https://github.com/The-Pocket/Tutorial-Codebase-Knowledge)