# Hydroshare _(hydroshare)_

HydroShare is a collaborative website being developed for better access to data and models in the hydrologic sciences.

#### Nightly Build Status generated by [Jenkins CI](http://ci.hydroshare.org:8080) (develop branch)

| Workflow | Clean | Build/Deploy | Unit Tests | Flake8 | Requirements |
| -------- | ----- | ------------ | ---------- | -------| ------------ |
| [![Build Status](http://ci.hydroshare.org:8080/job/nightly-build-workflow/badge/icon?style=plastic)](http://ci.hydroshare.org:8080/job/nightly-build-workflow/) | [![Build Status](http://ci.hydroshare.org:8080/job/nightly-build-clean/badge/icon?style=plastic)](http://ci.hydroshare.org:8080/job/nightly-build-clean/) | [![Build Status](http://ci.hydroshare.org:8080/job/nightly-build-deploy/badge/icon?style=plastic)](http://ci.hydroshare.org:8080/job/nightly-build-deploy/) | [![Build Status](http://ci.hydroshare.org:8080/job/nightly-build-test/badge/icon?style=plastic)](http://ci.hydroshare.org:8080/job/nightly-build-test/) | [![Build Status](http://ci.hydroshare.org:8080/job/nightly-build-flake8/badge/icon?style=plastic)](http://ci.hydroshare.org:8080/job/nightly-build-flake8/) | [![Requirements Status](https://requires.io/github/hydroshare/hs_docker_base/requirements.svg?branch=develop)](https://requires.io/github/hydroshare/hs_docker_base/requirements/?branch=master) | 

HydroShare is a collaborative website being developed for better access to data and models in the hydrologic sciences. HydroShare will provide the sustainable technology infrastructure needed to address critical issues related to water quantity, quality, accessibility, and management. HydroShare will expand the data sharing capability of the CUAHSI Hydrologic Information System by broadening the classes of data accommodated, expanding capability to include the sharing of models and model components, and taking advantage of emerging social media functionality to enhance information about and collaboration around hydrologic data and models. 

More information can be found in our [Wiki Pages](https://github.com/hydroshare/hydroshare/wiki)

## Install

This README file is for developers interested in working on the Hydroshare code itself, or for developers or researchers learning about how the application works at a deeper level. If you simply want to _use_ the application, go to http://hydroshare.org and register an account.

If you want to install and run the source code of application locally, read on.

#### Dependencies
[VirtualBox](https://www.virtualbox.org/wiki/Downloads) is required, as the preferred development environment is encapuslated within a VM. This VM has the appropriate version of Ubuntu  nstalled, as well as python and docker and other necessary development tools. 

### Simplified Installation Instructions 
1. Download the [latest OVA file here](http://distribution.hydroshare.org/public_html/)
2. Open the .OVA file with VirtualBox, this will create a guest VM
3. Follow the instructions here to share a local hydroshare folder with your guest VM
4. Start the guest VM
5. Log into the guest VM with either ssh or the GUI. The default username/password is hydro:hydro
6. From the root directory `/home/hydro`, clone this repository into the hydroshare folder
7. `cd` into the hydroshare folder and run `./hsctl rebuild --db` to build the application and run it
8. If all goes well, your local version of Hydroshare should be running at http://192.168.56.101:8000

For more detailed installation, please see this document: [Getting Started with HydroShare](https://github.com/hydroshare/hydroshare/wiki/getting_started)

## Usage

For all intents and purposes, Hydroshare is a large Python/Django application with some extra features and technologies added on:
- SOLR for searching
- Redis for caching
- RabbitMQ for concurrency and serialization
- iRODS for a federated file system
- PostgreSQL for the database backend

#### The `hsctl` Script

The `hsctl` script is your primary tool in interacting with and running tasks against your Hydroshare install. It has the syntax `./hsccl [command]` where `[command]` is one of:

- `loaddb`: Deletes existing database and reloads the database specified in the `hydroshare-config.yaml` file.
- `managepy [args]`: Executes a `python manage.py [args]` call on the running hydroshare container.
- `maint_off`: Removes the maintenance page from view (only if NGINX is being used).
- `maint_on`: Displays the maintenance page in the browser (only if NGINX is being used).
- `rebuild`: Stops, removes and deletes only the hydroshare docker containers and images while retaining the database contents on the subsequent build as defined in the `hydroshare-config.yaml` file
- `rebuild --db`: Fully stops, removes and deletes any prior hydroshare docker containers, images and database contents prior to installing a clean copy of the hydroshare codebase as defined in the `hydroshare-config.yaml` file.
- `rebuild_index`: Rebuilds the solr/haystack index in a non-interactive way.
- `restart`: Restarts the django server only (and nginx if applicable).
- `start`: Starts all containers as defined in the `docker-compose.yml` file (and nginx if applicable).
- `stop`: Stops all containers as defined in the `docker-compose.yml` file.
- `update_index`: Updates the solr/haystack index in a non-interactive way.

#### Testing and Debugging

Tests are run via normal Django tools and conventions. However, you should use the `hsctl` script mentioned abouve with the `managepy` command. For example: `./hsctl managepy test hs_core.tests.api.rest.test_resmap --keepdb`.

There are currently over 600 tests in the system, so it is highly recommended that you run the test suites separately from one another.
 
#### Local iRODS

Coming Soon

#### Local HTTPS

Coming Soon

## API

Coming Soon

## Contribute

Coming Soon

## License 

Coming Soon
