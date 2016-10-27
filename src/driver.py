from bpsRest import *
from cloudshell.api.cloudshell_api import CloudShellAPISession
from cloudshell.core.logger.qs_logger import get_qs_logger
from cloudshell.shell.core.resource_driver_interface import ResourceDriverInterface
from cloudshell.shell.core.driver_context import InitCommandContext, ResourceCommandContext, AutoLoadCommandContext, \
    AutoLoadAttribute, AutoLoadResource, AutoLoadDetails
from re import match


class IxiaBreakingPointDriver(ResourceDriverInterface):
    def cleanup(self):
        """
        Destroy the driver session, this function is called everytime a driver instance is destroyed
        This is a good place to close any open sessions, finish writing to log files
        """
        self.bps_session.logout()

    def __init__(self):
        """
        ctor must be without arguments, it is created with reflection at run time
        """
        self.bps_session = None
        self.cs_session = None
        self.last_test_id = None
        self.last_test_name = None
        self.logger = None
        self.requested_route = None
        self.reservation_description = None
        self.reservation_id = None
        self.resource_name = None
        self.test_id = None
        self.test_name = None
        self.topology_attribute = None

    def initialize(self, context):
        """
        Initialize the driver session, this function is called everytime a new instance of the driver is created
        This is a good place to load and cache the driver configuration, initiate sessions etc.
        :param InitCommandContext context: the context the command runs on

        """
        self.logger = get_qs_logger()
        self.resource_name = context.resource.name

        return

    def get_port_state(self, context):
        self._bps_session_handler(context)
        self._cs_session_handler(context)
        self.reservation_id = context.reservation.reservation_id

        port_state = self.bps_session.portsState()
        self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                        "[%s] Port state: %s" %
                                                        (self.resource_name,
                                                         port_state))
        return

    def get_real_time_statistics(self, context):
        self._bps_session_handler(context)
        self._cs_session_handler(context)
        self.reservation_id = context.reservation.reservation_id

        if self.test_id is None:
            self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                            "[%s] No test running" %
                                                            self.resource_name)
        else:
            rts = self.bps_session.getRTS(self.test_id)
            self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                            "[%s] %s(%s) statistics: %s" %
                                                            (self.resource_name,
                                                             self.test_name,
                                                             self.test_id,
                                                             rts))
        return

    def get_test_progress(self, context):
        self._bps_session_handler(context)
        self._cs_session_handler(context)
        self.reservation_id = context.reservation.reservation_id

        if self.test_id is None:
            self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                            "[%s] No test running" %
                                                            self.resource_name)
        else:
            progress = self.bps_session.getTestProgress(self.test_id)
            self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                            "[%s] %s(%s) %s%% complete" %
                                                            (self.resource_name,
                                                             self.test_name,
                                                             self.test_id,
                                                             int(progress)))
        return

    def get_test_results(self, context):
        self._bps_session_handler(context)
        self._cs_session_handler(context)
        self.reservation_id = context.reservation.reservation_id

        test_id = self.test_id if self.test_id is not None else self.last_test_id
        test_name = self.test_name if self.test_name is not None else self.last_test_name
        if test_id is None:
            self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                            "[%s] No results available" %
                                                            self.resource_name)
        else:
            raw_test_result = self.bps_session.getTestResult(test_id)
            test_result = raw_test_result[raw_test_result.rindex(' ') + 1:]
            self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                            "[%s] %s(%s) %s" %
                                                            (self.resource_name,
                                                             test_name,
                                                             test_id,
                                                             test_result))
        return

    def release_ports(self, slot, port_list):
        self.bps_session.unreservePorts(slot=slot, portList=port_list)

    def reserve_ports(self, slot, port_list, group, force=True):
        self.bps_session.reservePorts(slot=slot, portList=port_list, group=group, force=force)

        return

    def start_test(self, context):
        self._bps_session_handler(context)
        self._refresh_reservation_details(context)

        self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                        "[%s] topology_attribute: %s" %
                                                        (self.resource_name,
                                                         self.topology_attribute))

        last_test_name = self.test_name
        self.test_name = self.topology_attribute['Test Name']

        self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                        "[%s] test_name: %s" %
                                                        (self.resource_name,
                                                         self.test_name))
        try:
            last_test_id = self.test_id
            self.test_id = self.bps_session.runTest(modelname=self.test_name, group=2)
        except BPS.TestException as err:
            self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                            "[%s] Failed to start test, return code: %s - %s" %
                                                            (self.resource_name,
                                                             err.status_code,
                                                             err.message))
            raise
        except:
            raise

        self.cs_session.WriteMessageToReservationOutput(self.reservation_id, "[%s] %s(%s) started" %
                                                        (self.resource_name,
                                                         self.test_name,
                                                         self.test_id))
        self.last_test_id = last_test_id
        self.last_test_name = last_test_name

        return

    def stop_test(self, context):
        self._bps_session_handler(context)
        self._cs_session_handler(context)
        self.reservation_id = context.reservation.reservation_id

        if self.test_id is None:
            self.cs_session.WriteMessageToReservationOutput(self.reservation_id,
                                                            "[%s] No test running" %
                                                            self.resource_name)
        else:
            self.bps_session.stopTest(self.test_id)
            self.cs_session.WriteMessageToReservationOutput(self.reservation_id, "[%s] %s(%s) stopped" %
                                                            (self.resource_name,
                                                             self.test_name,
                                                             self.test_id))
            self.last_test_id = self.test_id
            self.last_test_name = self.test_name
            self.test_id = None
            self.test_name = None

        return

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

        return

    def _bps_session_handler(self, context):
        self._cs_session_handler(context)
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
                                                             err.message))
        return

    def _covert_topologies_resources_attribute_info(self):
        dictionary = {}
        for resource_attribute in self.reservation_description.TopologiesResourcesAttributeInfo:
            if resource_attribute.Name == self.resource_name:
                dictionary[resource_attribute.AttributeName] = resource_attribute.AttributeValue[0]

        return dictionary

    def _covert_requested_routes_info(self):
        dictionary = {}
        for requested_route in self.reservation_description.RequestedRoutesInfo:
            source = match(r'(?P<resource_name>.+)/Slot (?P<slot>\d+)/Port (?P<port>\d+)', requested_route.Source)
            if source is not None and source.group('resource_name') == self.resource_name:
                if source.group('slot') not in dictionary:
                    dictionary[source.group('slot')] = {}

                dictionary[source.group('slot')][source.group('port')] = requested_route.Target

            target = match(r'(?P<resource_name>.+)/Slot (?P<slot>\d+)/Port (?P<port>\d+)', requested_route.Target)
            if target is not None and target.group('resource_name') == self.resource_name:
                if target.group('slot') not in dictionary:
                    dictionary[target.group('slot')] = {}

                dictionary[target.group('slot')][target.group('port')] = requested_route.Source

        return dictionary

    def _refresh_reservation_details(self, context):
        self._cs_session_handler(context)
        self.reservation_id = context.reservation.reservation_id

        self.reservation_description = self.cs_session.GetReservationDetails(self.reservation_id).ReservationDescription
        self.requested_route = self._covert_requested_routes_info()
        self.topology_attribute = self._covert_topologies_resources_attribute_info()

        return

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
