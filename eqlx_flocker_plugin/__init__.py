from flocker.node import BackendDescription, DeployerType
from eqlx_flocker_plugin.eqlx import EqlxBlockDeviceAPI

def api_factory(cluster_id, **kwargs):
    return EqlxBlockDeviceAPI(
                        cluster_id=cluster_id,
                        username=kwargs[u"username"],
                        password=kwargs[u"password"],
                        eqlx_ip=kwargs["eqlx_ip"],
                        compute_instance_id=kwargs[u'compute_instance_id'])

FLOCKER_BACKEND = BackendDescription(
    name=u'eqlx_flocker_plugin',
    needs_reactor=False, needs_cluster_id=True,
    api_factory=api_factory,
    #required_config={"username","password", "eqlx_ip"},
    deployer_type=DeployerType.block)
