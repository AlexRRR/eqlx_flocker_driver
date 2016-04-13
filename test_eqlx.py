
from uuid import uuid4
import pdb
import imp
import os

from flocker.node.agents.test.test_blockdevice import make_iblockdeviceapi_tests

from twisted.trial.unittest import SynchronousTestCase, SkipTest
from eqlx_flocker_plugin.eqlx import (
    Eqlx,
    EqlxBlockDeviceAPI
)


ALLOCATION_SIZE = 1
ALOC_UNIT = 1085276160
EQLX_IP = u'{0}'.format(os.environ['EQLX_IP'])
EQLX_USER = u'{0}'.format(os.environ['EQLX_USER'])
EQLX_PASSWORD = u'{0}'.format(os.environ['EQLX_PASSWORD'])
HOST_IP = u'{0}'.format(os.environ['HOST_IP'])

def api_factory(test_case):
    eqlx = EqlxBlockDeviceAPI(cluster_id= unicode(uuid4()),
                                eqlx_ip=EQLX_IP,
                                username=EQLX_USER,
                                password=EQLX_PASSWORD,
                                compute_instance_id=HOST_IP)
    test_case.addCleanup(destroy_volumes, eqlx)
    return eqlx

def destroy_volumes(api):
    """
    Destroy all volumes created by API
    """
    volumes = api.list_volumes()
    for volume in volumes:
        print("would delete: %s" % volume.blockdevice_id)
        api.destroy_volume(volume.blockdevice_id)

class EqlxBlockDeviceAPIInterfaceTests(
    make_iblockdeviceapi_tests(
                        blockdevice_api_factory=(lambda test_case: api_factory(test_case=test_case)),
                        minimum_allocatable_size=ALLOCATION_SIZE,
                        device_allocation_unit=ALOC_UNIT,
                        unknown_blockdevice_id_factory=lambda test: unicode(uuid4()))):
            """
            Some tests
            """


if __name__ == "__main__":
    api = api_factory(True)
    destroy_volumes(api)
