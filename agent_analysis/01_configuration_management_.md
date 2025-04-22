# Chapter 1: Configuration Management

Welcome to the `agent` project tutorial! Imagine you have a tool that needs to log into several network devices. What happens if the login password changes? Or maybe you need to tell the tool how often to check the devices? Changing these details directly in the main code can be messy and risky. You might miss a spot, or accidentally break something else!

This is where **Configuration Management** comes in. It's like having a dedicated settings page or a central notebook for our `agent` application.

## What Problem Does This Solve?

Think about settings you might need for a network tool:
*   Usernames and passwords for devices.
*   The address of a central server (like NetBox).
*   Special keys (tokens) to access services.
*   How often to perform tasks (e.g., collect data every 5 minutes).
*   How many tasks to run at the same time.

Instead of scattering these details throughout different code files (which makes them hard to find and update), Configuration Management provides **one central place** to store and manage them.

In our `agent` project, this central place is a simple file named `config.py`.

## Our Configuration Notebook: `config.py`

Let's take a peek inside our "notebook", the `config.py` file. It holds the essential settings our application needs to run.

```python
# File: config.py

username = "admin"
password = "admin@123"
netbox_address = "10.27.200.47:8000"
netbox_token = "626e799179e45ee404516640114e9869ee4bb095"
update_time = 5
max_workers = 10
```

Let's break down what these settings mean:

*   `username` & `password`: These are the *default* login details used to connect to Juniper network devices. We'll see later how the code uses these.
*   `netbox_address`: This tells the application where to find your NetBox server (the IP address and port).
*   `netbox_token`: This is a special access key (API token) needed to securely interact with NetBox.
*   `update_time`: This controls how often, in minutes, the application should collect fresh data from the network devices and NetBox (set to 5 minutes here).
*   `max_workers`: This sets how many data collection tasks can run simultaneously. Running tasks in parallel can speed things up!

**Why is this useful?** If you need to change the default Juniper password, update the NetBox server address, or adjust the collection frequency, you only need to edit *this one file* (`config.py`). All other parts of the application will automatically pick up the changes next time they need these settings.

## How Other Parts Use the Configuration

So, how do other parts of the `agent` project access these settings from `config.py`? It's straightforward: they simply *import* the `config` file and then use the variable names.

**Example 1: Logging into Juniper Devices**

The code responsible for connecting to Juniper devices needs the username and password. Look at this snippet from `jun_collect.py`:

```python
# File: jun_collect.py (Simplified Snippet)

import config # <-- Import the configuration file

# ... other code ...

def rpc_devices(ip_host):
    # (Special handling for specific test IPs omitted for clarity)
    # Use the default username and password from config.py
    username = config.username # <-- Read username from config
    password = config.password # <-- Read password from config

    # ... code to connect using username and password ...
    try:
        # Connect using the retrieved credentials
        with manager.connect(
            host=ip_host,
            port=830, # Port is hardcoded here, could also be in config
            username=username,
            password=password,
            # ... other connection parameters ...
        ) as conn:
            # ... collect data ...
            pass # Placeholder for actual data collection logic
    except Exception as e:
        print(f"Error connecting to {ip_host}: {e}")

# ... other functions ...
```

See how easy that is?
1.  `import config` makes all the settings from `config.py` available.
2.  `config.username` gets the value of the `username` variable from `config.py`.
3.  `config.password` gets the value of the `password` variable from `config.py`.

*(Note: The full `jun_collect.py` code has a special check for specific IP addresses like "10.27.193.80" where it uses hardcoded "lab" credentials. For all other devices, it uses the default credentials from `config.py` as shown above.)*

**Example 2: Getting Data from NetBox**

Similarly, the code that talks to NetBox needs its address and access token. Here's a snippet from `parsing_netbox.py`:

```python
# File: parsing_netbox.py (Simplified Snippet)

import config # <-- Import the configuration file
import requests

netbox_address = config.netbox_address # <-- Read NetBox address
nb_token = 'Token ' + config.netbox_token # <-- Read NetBox token

headers = {
    'Accept': 'application/json',
    'Authorization': nb_token, # <-- Use the token in request headers
}

def get_netbox_devices():
    # Use the address to build the request URL
    url = f'http://{netbox_address}/api/dcim/devices/'
    # ... code to make the request using url and headers ...
    response = requests.request("GET", url, headers=headers, data={})
    # ... process the response ...
    return {} # Placeholder for actual result

# ... other functions ...
```

Again, it just imports `config` and uses `config.netbox_address` and `config.netbox_token`.

**Example 3: Controlling How Often and How Fast to Collect Data**

The main application logic in `main.py` uses the `update_time` and `max_workers` settings:

```python
# File: main.py (Simplified Snippet)

import schedule
import time
from concurrent.futures import ThreadPoolExecutor

import config # <-- Import the configuration file

# ... other imports and code ...

def collect_and_write_data():
    print("[INFO] Starting data collection...")
    # ...
    # Use max_workers to limit parallel tasks
    with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        # ... submit tasks to the executor ...
        pass # Placeholder
    # ...
    print("[INFO] Data collection complete.")

def run_scheduler():
    # Use update_time to schedule the job
    schedule.every(config.update_time).minutes.do(collect_and_write_data)

    while True:
        schedule.run_pending()
        time.sleep(1)

# ... main execution block ...
```

The scheduler uses `config.update_time` to know how frequently to run the `collect_and_write_data` function. The `ThreadPoolExecutor` uses `config.max_workers` to control how many device collections happen at the same time.

## Under the Hood: How Does It Work?

There's no magic involved! `config.py` is just a standard Python file. When another Python file (like `jun_collect.py`) executes the line `import config`, Python essentially runs `config.py` and makes all the variables defined in it accessible under the `config.` prefix.

Here’s a simple diagram showing the interaction:

```mermaid
sequenceDiagram
    participant Other Module as Other Module (e.g., jun_collect.py)
    participant ConfigFile as config.py

    Other Module->>ConfigFile: import config
    Note right of ConfigFile: config.py defines variables like 'username', 'netbox_address' etc.
    Other Module->>ConfigFile: Read config.username
    ConfigFile-->>Other Module: Return value of 'username' (e.g., "admin")
    Other Module->>ConfigFile: Read config.netbox_address
    ConfigFile-->>Other Module: Return value of 'netbox_address' (e.g., "10.27.200.47:8000")
```

This simple mechanism allows us to keep all our settings neatly organized in one place.

## Conclusion

In this chapter, we learned about Configuration Management in the `agent` project. We saw that:

*   It solves the problem of hardcoding settings directly into the code.
*   It uses a central file, `config.py`, to store key parameters like credentials, server addresses, and operational settings.
*   Other parts of the application easily access these settings by importing `config` and using `config.setting_name`.
*   This makes the application much easier to configure, update, and maintain.

Now that we understand how the application is configured, we're ready to see how it coordinates the work of collecting data from our network.

Next up, we'll dive into the "brain" of the operation: the [Data Collection Orchestrator](02_data_collection_orchestrator_.md). This component uses the settings we just learned about (`update_time`, `max_workers`) to manage the overall data gathering process from Juniper devices and NetBox.

---

Generated by [AI Codebase Knowledge Builder](https://github.com/The-Pocket/Tutorial-Codebase-Knowledge)