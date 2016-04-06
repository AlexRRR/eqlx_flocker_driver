
# Flocker driver for Dell Equallogic

## Installation

Build the plugin and distribute it to your flocker nodes.

```
python setup.py sdist
```

Using flocker's pip in each node, (Flocker uses its own environment) install the module for example:

```
/opt/flocker/bin/pip install /vagrant-data/eqlx_flocker_plugin-1.0.tar.gz
```

## Configuration

Once installed please configure your /etc/flocker/agent.yaml

```
"version": 1
"control-service":
   "hostname": "10.183.2.80"
   "port": 4524
"dataset":
   "backend": "eqlx_flocker_plugin"
   "username": "myuser"
   "password": "mypass"
   "eqlx_ip": "10.10.0.9"
   "cluster_id": "NAS"
```

## Testing

Functional testing of the block storage driver is done using flocker's provided test suite, using twisted's trail:

```
trail test_eqlx.py
```
