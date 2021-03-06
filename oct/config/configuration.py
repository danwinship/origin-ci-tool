# coding=utf-8
from __future__ import absolute_import, division, print_function

from os import getenv, listdir, mkdir
from os.path import abspath, exists, expanduser, isdir, join
from yaml import dump, load

from ..config.ansible_client import AnsibleCoreClient
from ..config.aws_client import AWSClientConfiguration
from ..config.aws_variables import AWSVariables
from ..config.vagrant import VagrantVMMetadata
from ..config.variables import PlaybookExtraVariables
from ..util.playbook import playbook_path

DEFAULT_HOSTNAME = 'openshiftdevel'

_ANSIBLE_CLIENT_CONFIGURATION_FILE = 'ansible_client_configuration.yml'
_ANSIBLE_VARIABLES_FILE = 'ansible_variables.yml'
_ANSIBLE_INVENTORY_DIRECTORY = 'inventory'
_VAGRANT_ROOT_DIRECTORY = 'vagrant'
_VAGRANT_BOX_DIRECTORY = 'boxes'
_LOG_DIRECTORY = 'logs'
_AWS_CLIENT_CONFIGURATION_FILE = 'aws_client_configuration.yml'
_AWS_VARIABLES_FILE = 'aws_variables.yml'


class Configuration(object):
    """
    This container holds all of the state that this tool needs
    to persist between CLI invocations. Default values allow
    for playbooks to be run with a minimal amount of specification.
    `run_playbook()` acts as a minimal client for the Ansible API.
    """

    def __init__(self):
        # Configuration will be placed in the user-based conf-
        # iguration path, preferring an explicit directory and
        # otherwise using $HOME.
        base_dir = getenv('OCT_CONFIG_HOME', abspath(join(expanduser('~'), '.config')))

        # path to the local configuration directory
        self._path = abspath(join(base_dir, 'origin-ci-tool'))

        self.initialize_directories()

        # configuration options for Ansible core
        self.ansible_client_configuration = None
        self.load_ansible_client_configuration()

        # extra variables we want to send to Ansible playbooks
        self.ansible_variables = None
        self.load_ansible_variables()

        # metadata about active Vagrant local VMs
        self._vagrant_metadata = []
        self.load_vagrant_metadata()

        # configuration options for AWS client
        self.aws_client_configuration = None
        self.load_aws_client_configuration()

        # extra variables we want to send to Ansible playbooks
        # that touch the AWS API
        self.aws_variables = None
        self.load_aws_variables()

    def initialize_directories(self):
        """
        Initialize directories on the filesystem that we will
        expect to exist in the future.
        """
        directories = [
            self._path,
            self.ansible_log_path,
            self.vagrant_directory_root
        ]
        for directory in directories:
            if not exists(directory):
                mkdir(directory)

    def run_playbook(self, playbook_relative_path, playbook_variables=None, option_overrides=None):
        """
        Run a playbook from file with the variables provided. The
        playbook file should be specified as a relative path from
        the root of the internal Ansible playbook directory, with
        the YAML suffix omitted, e.g. `prepare/main`

        :param playbook_relative_path: the location of the playbook
        :param playbook_variables: extra variables for the playbook
        """
        playbook_variables = self.ansible_variables.default(
            self.aws_variables.default(playbook_variables)
        )

        self.ansible_client_configuration.run_playbook(
            playbook_file=playbook_path(playbook_relative_path),
            playbook_variables=playbook_variables,
            option_overrides=option_overrides
        )

    @property
    def ansible_inventory_path(self):
        """
        Yield the path to the Ansible core inventory directory.
        :return: absolute path to the Ansible core inventory directory
        """
        return join(self._path, _ANSIBLE_INVENTORY_DIRECTORY)

    @property
    def ansible_client_configuration_path(self):
        """
        Yield the path to the Ansible core configuration file.
        :return: absolute path to the Ansible core configuration
        """
        return join(self._path, _ANSIBLE_CLIENT_CONFIGURATION_FILE)

    def load_ansible_client_configuration(self):
        """
        Load the Ansible core configuration options from disk,
        or if they have not yet been written to disk, use the
        default values and write them for future callers.
        """
        if not exists(self.ansible_client_configuration_path):
            self.ansible_client_configuration = AnsibleCoreClient(
                inventory_dir=self.ansible_inventory_path,
                log_directory=self.ansible_log_path
            )
            self.write_ansible_client_configuration()
        else:
            with open(self.ansible_client_configuration_path) as configuration_file:
                self.ansible_client_configuration = load(configuration_file)

    def write_ansible_client_configuration(self):
        """
        Write the current set of Ansible core configuration
        options to disk.
        """
        with open(self.ansible_client_configuration_path, 'w+') as configuration_file:
            dump(
                self.ansible_client_configuration,
                configuration_file,
                default_flow_style=False,
                explicit_start=True
            )

    @property
    def variables_path(self):
        """
        Yield the path to the Ansible playbook extra variables file.
        :return: absolute path to the Ansible playbook extra variables
        """
        return join(self._path, _ANSIBLE_VARIABLES_FILE)

    def load_ansible_variables(self):
        """
        Load the Ansible extra playbook variables from disk,
        or if they have not yet been written to disk, use the
        default values and write them for future callers.
        """
        if not exists(self.variables_path):
            self.ansible_variables = PlaybookExtraVariables()
            self.write_ansible_variables()
        else:
            with open(self.variables_path) as variables_file:
                self.ansible_variables = load(variables_file)

    def write_ansible_variables(self):
        """
        Write the current set of Ansible extra playbook
        variables to disk.
        """
        with open(self.variables_path, 'w+') as variables_file:
            dump(
                self.ansible_variables,
                variables_file,
                default_flow_style=False,
                explicit_start=True
            )

    @property
    def vagrant_directory_root(self):
        """
        Yield the root path for Vagrant VM locations.
        :return: absolute path to Vagrant VM containers directory
        """
        return join(self._path, _VAGRANT_ROOT_DIRECTORY)

    @property
    def vagrant_box_directory(self):
        """
        Yield the path for Vagrant box files and metadata.
        :return: absolute path to Vagrant VM boxes directory
        """
        return join(self.vagrant_directory_root, _VAGRANT_BOX_DIRECTORY)

    def vagrant_home_directory(self, name):
        """
        Yield the path to the specific storage directory
        for the VM `boxname'.

        :param name: name of the VM
        :return: absolute path to the Vagrant VM directory
        """
        return join(self.vagrant_directory_root, name)

    @property
    def next_available_vagrant_name(self):
        """
        Yield the next available hostname for a local Vagrant
        VM.

        :return: the next hostname
        """
        if not self._vagrant_hostname_taken(DEFAULT_HOSTNAME):
            return DEFAULT_HOSTNAME

        for i in range(len(listdir(self.vagrant_directory_root)) + 1):
            possible_hostname = DEFAULT_HOSTNAME + str(i)
            if not self._vagrant_hostname_taken(possible_hostname):
                return possible_hostname

    def _vagrant_hostname_taken(self, name):
        """
        Determine if a Vagrant VM with the given hostname exists.

        :param name: hostname of the VM
        :return: whether or not the VM exists
        """
        # we know all of our Vagrant VMs must reside in top-
        # level subdirectories of the Vagrant directory root,
        # so we can do this simple exists check
        return isdir(join(self.vagrant_directory_root, name))

    def load_vagrant_metadata(self):
        """
        Load metadata for the Vagrant virtual machines
        that we have provisioned with this tool.
        """
        if not exists(self.vagrant_directory_root):
            mkdir(self.vagrant_directory_root)
        else:
            for content in listdir(self.vagrant_directory_root):
                variables_file = join(self.vagrant_directory_root, content, 'variables.yml')
                groups_file = join(self.vagrant_directory_root, content, 'groups.yml')
                if exists(variables_file):
                    self.register_vagrant_host(VagrantVMMetadata(variable_file=variables_file, group_file=groups_file))

    def registered_vagrant_machines(self):
        """
        Yield the list of Vagrant machine metadata.
        :return: the Vagrant metadata
        """
        return self._vagrant_metadata

    def register_vagrant_host(self, data):
        """
        Register a new host by updating metadata records for the
        new VM both in the in-memory cache for this process and
        the on-disk records that will persist past this CLI call.

        :param data: VagrantVMMetadata for the host
        """
        if not isinstance(data, VagrantVMMetadata):
            raise TypeError('Registering a machine requires {}, got {} instead!'.format(type(VagrantVMMetadata), type(data)))
        else:
            self._vagrant_metadata.append(data)
            data.write()

    @property
    def ansible_log_path(self):
        """
        Yield the root path for Ansible log files.
        :return: absolute path to Ansible logging directory
        """
        return join(self._path, _LOG_DIRECTORY)

    @property
    def aws_client_configuration_path(self):
        """
        Yield the path to the AWS client configuration file.
        :return: absolute path to the AWS client configuration
        """
        return join(self._path, _AWS_CLIENT_CONFIGURATION_FILE)

    def load_aws_client_configuration(self):
        """
        Load the AWS client configuration from disk, or if
        they have not yet been written to disk, use the
        default values and write them for future callers.
        """
        if not exists(self.aws_client_configuration_path):
            self.aws_client_configuration = AWSClientConfiguration()
            self.write_aws_client_configuration()
        else:
            with open(self.aws_client_configuration_path) as aws_client_configuration_file:
                self.aws_client_configuration = load(aws_client_configuration_file)

    def write_aws_client_configuration(self):
        """
        Write the current set of AWS client configuration
        variables to disk.
        """
        with open(self.aws_client_configuration_path, 'w+') as aws_client_configuration_file:
            dump(
                self.aws_client_configuration,
                aws_client_configuration_file,
                default_flow_style=False,
                explicit_start=True
            )

    @property
    def aws_variables_path(self):
        """
        Yield the path to the AWS client configuration file.
        :return: absolute path to the AWS client configuration
        """
        return join(self._path, _AWS_VARIABLES_FILE)

    def load_aws_variables(self):
        """
        Load the AWS client configuration from disk, or if
        they have not yet been written to disk, use the
        default values and write them for future callers.
        """
        if not exists(self.aws_variables_path):
            self.aws_variables = AWSVariables()
            self.write_aws_variables()
        else:
            with open(self.aws_variables_path) as aws_variables_file:
                self.aws_variables = load(aws_variables_file)

    def write_aws_variables(self):
        """
        Write the current set of AWS client configuration
        variables to disk.
        """
        with open(self.aws_variables_path, 'w+') as aws_variables_file:
            dump(
                self.aws_variables,
                aws_variables_file,
                default_flow_style=False,
                explicit_start=True
            )
