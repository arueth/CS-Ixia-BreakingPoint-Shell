from bpsRest import *
from pprint import pprint
from cloudshell.api.cloudshell_api import CloudShellAPISession
from cloudshell.core.logger.qs_logger import get_qs_logger
from cloudshell.shell.core.resource_driver_interface import ResourceDriverInterface
from cloudshell.shell.core.driver_context import InitCommandContext, ResourceCommandContext, AutoLoadCommandContext, \
    AutoLoadAttribute, AutoLoadResource, AutoLoadDetails


class IxiaBreakingPointDriver(ResourceDriverInterface):
    def cleanup(self):
        """
        Destroy the driver session, this function is called everytime a driver instance is destroyed
        This is a good place to close any open sessions, finish writing to log files
        """
        self.cs_session.WriteMessageToReservationOutput(self.reservation_id, "[%s] Logging out" % self.resource_name)
        self.bps_session.logout()

    def __init__(self):
        """
        ctor must be without arguments, it is created with reflection at run time
        """
        self.bps_session = None
        self.cs_session = None
        self.reservation_id = None
        self.resource_name = None

    def initialize(self, context):
        """
        Initialize the driver session, this function is called everytime a new instance of the driver is created
        This is a good place to load and cache the driver configuration, initiate sessions etc.
        :param InitCommandContext context: the context the command runs on

        """
        self.logger = get_qs_logger()
        self.resource_name = context.resource.name

    def get_port_state(self, context):
        self._bps_session_handler(context)
        self._cs_session_handler(context)
        self.reservation_id = context.reservation.reservation_id

        port_state = self.bps_session.portsState()
        self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                        "[%s] Port state:\n%s" % (
                                                            self.resource_name, pprint(port_state)))

        return port_state

    def run_test(self, context):
        self._bps_session_handler(context)
        self._cs_session_handler(context)
        self.reservation_id = context.reservation.reservation_id

        res = self.cs_session.GetReservationDetails(self.reservation_id)
        topo_att = res.ReservationDescription.TopologiesResourcesAttributeInfo
        for item in topo_att:
            if item.AttributeName == 'Test Name':
                self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                                str(item.AttributeValue).strip('[]\''))
                test_name = str(item.AttributeValue).strip('[]\'')

        self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                        "[%s] Reserving ports" % self.resource_name)
        self.bps_session.reservePorts(slot=1, portList=[0, 1], group=1, force=True)

        try:
            test_id = self.bps_session.runTest(modelname=test_name, group=1)
        except BPS.TestException as err:
            self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                            "[%s] Failed to start test, return code: %s - %s" % (
                                                                self.resource_name, err.status_code, err.message))
            raise
        except:
            raise

        self.cs_session.WriteMessageToReservationOutput(self.reservation_id, "[%s] Running test '%s' with ID %s" % (
            self.resource_name, test_name, test_id))

        progress = 0
        while (progress < 100):
            progress = self.bps_session.getRTS(test_id)
            # self.cs_session.WriteMessageToReservationOutput(self.reservation_id, "%s%%" % progress)
            time.sleep(1)
        time.sleep(1)

        test_result = self.bps_session.getTestResult(test_id)
        self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                        "[%s] %s" % (self.resource_name, test_result))

        self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                        "[%s] Releasing ports" % self.resource_name)
        self.bps_session.unreservePorts(slot=1, portList=[0, 1])

    def _cs_session_handler(self, context):
        for attempt in range(3):
            try:
                self.cs_session = CloudShellAPISession(host=context.connectivity.server_address,
                                                       token_id=context.connectivity.admin_auth_token,
                                                       domain=context.reservation.domain)
            except:
                continue
            else:
                break
        else:
            raise

    def _bps_session_handler(self, context):
        self.resource_name = context.resource.name

        address = context.resource.address
        password_hash = context.resource.attributes['API Password']
        username = context.resource.attributes['API User']
        try:
            self.bps_session = BPS(address, username, self.cs_session.DecryptPassword(password_hash).Value)
            self.bps_session.login()
        except BPS.LoginException as err:
            self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                            "[%s] Failed to login, return code: %s - %s" %
                                                            (self.resource_name,
                                                             err.status_code,
                                                             err.message)
                                                            )

    # <editor-fold desc="Orchestration Save and Restore Standard">
    def orchestration_save(self, context, cancellation_context, mode, custom_params=None):
        """
        Saves the Shell state and returns a description of the saved artifacts and information
        This command is intended for API use only by sandbox orchestration scripts to implement
        a save and restore workflow
        :param ResourceCommandContext context: the context object containing resource and reservation info
        :param CancellationContext cancellation_context: Object to signal a request for cancellation. Must be enabled in drivermetadata.xml as well
        :param str mode: Snapshot save mode, can be one of two values 'shallow' (default) or 'deep'
        :param str custom_params: Set of custom parameters for the save operation
        :return: SavedResults serialized as JSON
        :rtype: OrchestrationSaveResult
        """

        # See below an example implementation, here we use jsonpickle for serialization,
        # to use this sample, you'll need to add jsonpickle to your requirements.txt file
        # The JSON schema is defined at: https://github.com/QualiSystems/sandbox_orchestration_standard/blob/master/save%20%26%20restore/saved_artifact_info.schema.json
        # You can find more information and examples examples in the spec document at https://github.com/QualiSystems/sandbox_orchestration_standard/blob/master/save%20%26%20restore/save%20%26%20restore%20standard.md
        '''
        # By convention, all dates should be UTC
        created_date = datetime.datetime.utcnow()

        # This can be any unique identifier which can later be used to retrieve the artifact
        # such as filepath etc.

        # By convention, all dates should be UTC
        created_date = datetime.datetime.utcnow()

        # This can be any unique identifier which can later be used to retrieve the artifact
        # such as filepath etc.
        identifier = created_date.strftime('%y_%m_%d %H_%M_%S_%f')

        orchestration_saved_artifact = OrchestrationSavedArtifact('REPLACE_WITH_ARTIFACT_TYPE', identifier)

        saved_artifacts_info = OrchestrationSavedArtifactInfo(
            resource_name="some_resource",
            created_date=created_date,
            restore_rules=OrchestrationRestoreRules(requires_same_resource=True),
            saved_artifact=orchestration_saved_artifact)

        return OrchestrationSaveResult(saved_artifacts_info)
        '''
        pass

    def orchestration_restore(self, context, cancellation_context, saved_details):
        """
        Restores a saved artifact previously saved by this Shell driver using the orchestration_save function
        :param ResourceCommandContext context: The context object for the command with resource and reservation info
        :param CancellationContext cancellation_context: Object to signal a request for cancellation. Must be enabled in drivermetadata.xml as well
        :param str saved_details: A JSON string representing the state to restore including saved artifacts and info
        :return: None
        """
        '''
        # The saved_details JSON will be defined according to the JSON Schema and is the same object returned via the
        # orchestration save function.
        # Example input:
        # {
        #     "saved_artifact": {
        #      "artifact_type": "REPLACE_WITH_ARTIFACT_TYPE",
        #      "identifier": "16_08_09 11_21_35_657000"
        #     },
        #     "resource_name": "some_resource",
        #     "restore_rules": {
        #      "requires_same_resource": true
        #     },
        #     "created_date": "2016-08-09T11:21:35.657000"
        #    }

        # The example code below just parses and prints the saved artifact identifier
        saved_details_object = json.loads(saved_details)
        return saved_details_object[u'saved_artifact'][u'identifier']
        '''
        pass

    # </editor-fold>


    # <editor-fold desc="Discovery">

    def get_inventory(self, context):
        """
        Discovers the resource structure and attributes.
        :param AutoLoadCommandContext context: the context the command runs on
        :return Attribute and sub-resource information for the Shell resource you can return an AutoLoadDetails object
        :rtype: AutoLoadDetails
        """
        # See below some example code demonstrating how to return the resource structure
        # and attributes. In real life, of course, if the actual values are not static,
        # this code would be preceded by some SNMP/other calls to get the actual resource information
        '''
           # Add sub resources details
           sub_resources = [ AutoLoadResource(model ='Generic Chassis',name= 'Chassis 1', relative_address='1'),
           AutoLoadResource(model='Generic Module',name= 'Module 1',relative_address= '1/1'),
           AutoLoadResource(model='Generic Port',name= 'Port 1', relative_address='1/1/1'),
           AutoLoadResource(model='Generic Port', name='Port 2', relative_address='1/1/2'),
           AutoLoadResource(model='Generic Power Port', name='Power Port', relative_address='1/PP1')]


           attributes = [ AutoLoadAttribute(relative_address='', attribute_name='Location', attribute_value='Santa Clara Lab'),
                          AutoLoadAttribute('', 'Model', 'Catalyst 3850'),
                          AutoLoadAttribute('', 'Vendor', 'Cisco'),
                          AutoLoadAttribute('1', 'Serial Number', 'JAE053002JD'),
                          AutoLoadAttribute('1', 'Model', 'WS-X4232-GB-RJ'),
                          AutoLoadAttribute('1/1', 'Model', 'WS-X4233-GB-EJ'),
                          AutoLoadAttribute('1/1', 'Serial Number', 'RVE056702UD'),
                          AutoLoadAttribute('1/1/1', 'MAC Address', 'fe80::e10c:f055:f7f1:bb7t16'),
                          AutoLoadAttribute('1/1/1', 'IPv4 Address', '192.168.10.7'),
                          AutoLoadAttribute('1/1/2', 'MAC Address', 'te67::e40c:g755:f55y:gh7w36'),
                          AutoLoadAttribute('1/1/2', 'IPv4 Address', '192.168.10.9'),
                          AutoLoadAttribute('1/PP1', 'Model', 'WS-X4232-GB-RJ'),
                          AutoLoadAttribute('1/PP1', 'Port Description', 'Power'),
                          AutoLoadAttribute('1/PP1', 'Serial Number', 'RVE056702UD')]

           return AutoLoadDetails(sub_resources,attributes)
        '''
        pass

    # </editor-fold>


    # <editor-fold desc="Health Check">

    def health_check(self, cancellation_context):
        """
        Checks if the device is up and connectable
        :return: None
        :exception Exception: Raises an error if cannot connect
        """
        pass

    # </editor-fold>


    def cleanup(self):
        """
        Destroy the driver session, this function is called everytime a driver instance is destroyed
        This is a good place to close any open sessions, finish writing to log files
        """
        pass
