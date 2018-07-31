import json
import logging
import os

from django.core.exceptions import ValidationError
from django.http import HttpResponse

from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound, status, PermissionDenied, \
    ValidationError as DRF_ValidationError

from django_irods.icommands import SessionException
from hs_core.hydroshare.utils import get_file_mime_type, resolve_request
from hs_core.models import ResourceFile

from hs_core.views.utils import authorize, ACTION_TO_AUTHORIZE, zip_folder, unzip_file, \
    create_folder, remove_folder, move_or_rename_file_or_folder, move_to_folder, \
    rename_file_or_folder, get_coverage_data_dict, irods_path_is_directory

logger = logging.getLogger(__name__)


def data_store_structure(request):
    """
    Get file hierarchy (collection of subcollections and data objects) for the requested directory
    in hydroshareZone or any federated zone used for HydroShare resource backend store.
    It is invoked by an AJAX call and returns json object that holds content for files
    and folders under the requested directory/collection/subcollection.
    The AJAX request must be a POST request with input data passed in for res_id and store_path
    where store_path is the relative path under res_id collection/directory
    """
    res_id = request.POST.get('res_id', None)
    if res_id is None:
        logger.error("no resource id in request")
        return HttpResponse('Bad request - resource id is not included',
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    res_id = str(res_id).strip()
    try:
        resource, _, _ = authorize(request, res_id,
                                   needed_permission=ACTION_TO_AUTHORIZE.VIEW_RESOURCE)
    except NotFound:
        logger.error("resource {} not found".format(res_id))
        return HttpResponse('Bad request - resource not found', status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied:
        logger.error("permission denied for resource {}".format(res_id))
        return HttpResponse('Permission denied', status=status.HTTP_401_UNAUTHORIZED)

    store_path = request.POST.get('store_path', None)
    if store_path is None:
        logger.error("store_path not included for resource {}".format(res_id))
        return HttpResponse('Bad request - store_path is not included',
                            status=status.HTTP_400_BAD_REQUEST)
    store_path = str(store_path).strip()
    if not store_path:
        logger.error("store_path empty for resource {}".format(res_id))
        return HttpResponse('Bad request - store_path cannot be empty',
                            status=status.HTTP_400_BAD_REQUEST)

    if not store_path.startswith('data/contents'):
        logger.error("store_path doesn't start with data/contents for resource {}".format(res_id))
        return HttpResponse('Bad request - store_path must start with data/contents/',
                            status=status.HTTP_400_BAD_REQUEST)

    if store_path.find('/../') >= 0 or store_path.endswith('/..'):
        logger.error("store_path cannot contain .. for resource {}".format(res_id))
        return HttpResponse('Bad request - store_path cannot contain /../',
                            status=status.HTTP_400_BAD_REQUEST)

    istorage = resource.get_irods_storage()
    directory_in_irods = os.path.join(resource.root_path, store_path)
    logger.debug("directory in irods = {}".format(directory_in_irods))

    try:
        store = istorage.listdir(directory_in_irods)
    except SessionException as ex:
        logger.error("session exception querying store_path {} for {}".format(store_path, res_id))
        return HttpResponse(ex.stderr, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    files = []
    dirs = []
    for dname in store[0]:     # directories
        d_pk = dname.decode('utf-8')
        d_url = resource.get_url_of_path(os.path.join(store_path, d_pk))
        logger.debug("d_url is {}".format(d_url))
        main_file = ''
        folder_aggregation_type = ''
        folder_aggregation_name = ''
        folder_aggregation_id = ''
        folder_aggregation_type_to_set = ''
        folder_store_path = os.path.join(store_path, d_pk)
        if resource.resource_type == "CompositeResource":
            dir_path = os.path.join(resource.short_id, folder_store_path)
            # find if this folder *dir_path* represents (contains) an aggregation object
            aggregation_object = resource.get_folder_aggregation_object(dir_path)
            # folder aggregation type is not relevant for single file aggregation types - which
            # are: GenericLogicalFile, and RefTimeseriesLogicalFile
            if aggregation_object is not None and not \
                    aggregation_object.is_single_file_aggregation:
                folder_aggregation_type = aggregation_object.get_aggregation_class_name()
                folder_aggregation_name = aggregation_object.get_aggregation_display_name()
                folder_aggregation_id = aggregation_object.id
                main_file = aggregation_object.get_main_file.file_name
            else:
                # find if any aggregation type can be created from this folder
                folder_aggregation_type_to_set = resource.get_folder_aggregation_type_to_set(
                    dir_path)
                if folder_aggregation_type_to_set is None:
                    folder_aggregation_type_to_set = ""
        dirs.append({'name': d_pk,
                     'url': d_url,
                     'main_file': main_file,
                     'folder_aggregation_type': folder_aggregation_type,
                     'folder_aggregation_name': folder_aggregation_name,
                     'folder_aggregation_id': folder_aggregation_id,
                     'folder_aggregation_type_to_set': folder_aggregation_type_to_set,
                     'folder_short_path': os.path.join(store_path, d_pk)})  # this is NOT short path

    for fname in store[1]:  # files
        fname = fname.decode('utf-8')
        file_in_irods = os.path.join(directory_in_irods, fname)
        size = istorage.size(file_in_irods)
        mtype = get_file_mime_type(fname)
        idx = mtype.find('/')
        if idx >= 0:
            mtype = mtype[idx + 1:]
        f_pk = ''
        f_url = ''
        logical_file_type = ''
        logical_file_id = ''
        aggregation_name = ''
        for f in ResourceFile.objects.filter(object_id=resource.id):
            if file_in_irods == f.storage_path:
                f_pk = f.pk
                f_url = f.url
                if resource.resource_type == "CompositeResource":
                    if f.has_logical_file:
                        logical_file_type = f.logical_file_type_name
                        logical_file_id = f.logical_file.id
                        aggregation_name = f.aggregation_display_name
                break

        if f_pk:  # file is found in Django
            logger.debug("file url is {}".format(f_url))
            files.append({'name': fname, 'size': size, 'type': mtype, 'pk': f_pk, 'url': f_url,
                          'aggregation_name': aggregation_name,
                          'logical_type': logical_file_type,
                          'logical_file_id': logical_file_id})
        else:  # file is not found in Django
            logger.error("data_store_structure: filename {} in iRODs has no analogue in Django"
                         .format(file_in_irods))

    return_object = {'files': files,
                     'folders': dirs,
                     'can_be_public': resource.can_be_public_or_discoverable}

    if resource.resource_type == "CompositeResource":
        return_object['spatial_coverage'] = get_coverage_data_dict(resource)
        return_object['temporal_coverage'] = get_coverage_data_dict(resource,
                                                                    coverage_type='temporal')
    return HttpResponse(
        json.dumps(return_object),
        content_type="application/json"
    )


def to_external_url(url):
    """
    Convert an internal download file/folder url to the external url.  This should eventually be
    replaced with with a reverse method that gets the correct mapping.
    """
    return url.replace("django_irods/download", "resource", 1)


def data_store_folder_zip(request, res_id=None):
    """
    Zip requested files and folders into a zip file in hydroshareZone or any federated zone
    used for HydroShare resource backend store. It is invoked by an AJAX call and returns
    json object that holds the created zip file name if it succeeds, and an empty string
    if it fails. The AJAX request must be a POST request with input data passed in for
    res_id, input_coll_path, output_zip_file_name, and remove_original_after_zip where
    input_coll_path is the relative sub-collection path under res_id collection to be zipped,
    output_zip_file_name is the file name only with no path of the generated zip file name,
    and remove_original_after_zip has a value of "true" or "false" (default is "true") indicating
    whether original files will be deleted after zipping.
    """
    res_id = request.POST.get('res_id', res_id)
    if res_id is None:
        return HttpResponse('Bad request - resource id is not included',
                            status=status.HTTP_400_BAD_REQUEST)
    res_id = str(res_id).strip()
    try:
        resource, _, user = authorize(request, res_id,
                                      needed_permission=ACTION_TO_AUTHORIZE.EDIT_RESOURCE)
    except NotFound:
        return HttpResponse('Bad request - resource not found', status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied:
        return HttpResponse('Permission denied', status=status.HTTP_401_UNAUTHORIZED)

    input_coll_path = resolve_request(request).get('input_coll_path', None)
    if input_coll_path is None:
        return HttpResponse('Bad request - input_coll_path is not included',
                            status=status.HTTP_400_BAD_REQUEST)
    input_coll_path = str(input_coll_path).strip()
    if not input_coll_path:
        return HttpResponse('Bad request - input_coll_path cannot be empty',
                            status=status.HTTP_400_BAD_REQUEST)

    if not input_coll_path.startswith('data/contents/'):
        return HttpResponse('Bad request - input_coll_path must start with data/contents/',
                            status=status.HTTP_400_BAD_REQUEST)

    if input_coll_path.find('/../') >= 0 or input_coll_path.endswith('/..'):
        return HttpResponse('Bad request - input_coll_path must not contain /../',
                            status=status.HTTP_400_BAD_REQUEST)

    output_zip_fname = resolve_request(request).get('output_zip_file_name', None)
    if output_zip_fname is None:
        return HttpResponse('Bad request - output_zip_fname is not included',
                            status=status.HTTP_400_BAD_REQUEST)
    output_zip_fname = str(output_zip_fname).strip()
    if not output_zip_fname:
        return HttpResponse('Bad request - output_zip_fname cannot be empty',
                            status=status.HTTP_400_BAD_REQUEST)

    if output_zip_fname.find('/') >= 0:
        return HttpResponse('Bad request - output_zip_fname cannot contain /',
                            status=status.HTTP_400_BAD_REQUEST)

    remove_original = resolve_request(request).get('remove_original_after_zip', None)
    bool_remove_original = True
    if remove_original:
        remove_original = str(remove_original).strip().lower()
        if remove_original == 'false':
            bool_remove_original = False

    try:
        output_zip_fname, size = \
            zip_folder(user, res_id, input_coll_path, output_zip_fname, bool_remove_original)
    except SessionException as ex:
        return HttpResponse(ex.stderr, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except DRF_ValidationError as ex:
        return HttpResponse(ex.detail, status=status.HTTP_400_BAD_REQUEST)

    return_object = {'name': output_zip_fname,
                     'size': size,
                     'type': 'zip'}

    return HttpResponse(
        json.dumps(return_object),
        content_type="application/json"
    )


@api_view(['POST'])
def data_store_folder_zip_public(request, pk):
    return data_store_folder_zip(request, res_id=pk)


def data_store_folder_unzip(request, **kwargs):
    """
    Unzip requested zip file while preserving folder structures in hydroshareZone or
    any federated zone used for HydroShare resource backend store. It is invoked by an AJAX call,
    and returns json object that holds the root path that contains the zipped content if it
    succeeds, and an empty string if it fails. The AJAX request must be a POST request with
    input data passed in for res_id, zip_with_rel_path, and remove_original_zip where
    zip_with_rel_path is the zip file name with relative path under res_id collection to be
    unzipped, and remove_original_zip has a value of "true" or "false" (default is "true")
    indicating whether original zip file will be deleted after unzipping.
    """
    res_id = request.POST.get('res_id', kwargs.get('res_id'))
    if res_id is None:
        return HttpResponse('Bad request - resource id is not included',
                            status=status.HTTP_400_BAD_REQUEST)
    res_id = str(res_id).strip()
    try:
        resource, _, user = authorize(request, res_id,
                                      needed_permission=ACTION_TO_AUTHORIZE.EDIT_RESOURCE)
    except NotFound:
        return HttpResponse('Bad request - resource not found', status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied:
        return HttpResponse('Permission denied', status=status.HTTP_401_UNAUTHORIZED)

    zip_with_rel_path = request.POST.get('zip_with_rel_path', kwargs.get('zip_with_rel_path'))
    if zip_with_rel_path is None:
        return HttpResponse('Bad request - zip_with_rel_path is not included',
                            status=status.HTTP_400_BAD_REQUEST)

    zip_with_rel_path = str(zip_with_rel_path).strip()
    if not zip_with_rel_path:
        return HttpResponse('Bad request - zip_with_rel_path cannot be empty',
                            status=status.HTTP_400_BAD_REQUEST)

    # security checks deny illicit requests
    if not zip_with_rel_path.startswith('data/contents/'):
        return HttpResponse('Bad request - zip_with_rel_path must start with data/contents/',
                            status=status.HTTP_400_BAD_REQUEST)
    if zip_with_rel_path.find('/../') >= 0 or zip_with_rel_path.endswith('/..'):
        return HttpResponse('Bad request - zip_with_rel_path must not contain /../',
                            status=status.HTTP_400_BAD_REQUEST)

    remove_original = request.POST.get('remove_original_zip', None)
    bool_remove_original = True
    if remove_original:
        remove_original = str(remove_original).strip().lower()
        if remove_original == 'false':
            bool_remove_original = False

    try:
        unzip_file(user, res_id, zip_with_rel_path, bool_remove_original)
    except SessionException as ex:
        specific_msg = "iRODS error resulted in unzip being cancelled. This may be due to " \
                       "protection from overwriting existing files. Unzip in a different " \
                       "location (e.g., folder) or move or rename the file being overwritten. " \
                       "iRODS error follows: "
        return HttpResponse(specific_msg + ex.stderr, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except DRF_ValidationError as ex:
        return HttpResponse(ex.detail, status=status.HTTP_400_BAD_REQUEST)

    # this unzipped_path can be used for POST request input to data_store_structure()
    # to list the folder structure after unzipping
    return_object = {'unzipped_path': os.path.dirname(zip_with_rel_path)}

    return HttpResponse(
        json.dumps(return_object),
        content_type="application/json"
    )


@api_view(['POST'])
def data_store_folder_unzip_public(request, pk, pathname):
    """
    Public version of data_store_folder_unzip, incorporating path variables

    :param request:
    :param pk:
    :param pathname:
    :return HttpResponse:
    """

    sys_pathname = 'data/contents/%s' % pathname
    return data_store_folder_unzip(request, res_id=pk, zip_with_rel_path=sys_pathname)


def data_store_create_folder(request):
    """
    create a sub-folder/sub-collection in hydroshareZone or any federated zone used for HydroShare
    resource backend store. It is invoked by an AJAX call and returns json object that has the
    relative path of the new folder created if succeeds, and return empty string if fails. The
    AJAX request must be a POST request with input data passed in for res_id and folder_path
    where folder_path is the relative path for the new folder to be created under
    res_id collection/directory.
    """
    res_id = request.POST.get('res_id', None)
    if res_id is None:
        return HttpResponse('Bad request - resource id is not included',
                            status=status.HTTP_400_BAD_REQUEST)
    res_id = str(res_id).strip()
    try:
        resource, _, _ = authorize(request, res_id,
                                   needed_permission=ACTION_TO_AUTHORIZE.EDIT_RESOURCE)
    except NotFound:
        return HttpResponse('Bad request - resource not found', status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied:
        return HttpResponse('Permission denied', status=status.HTTP_401_UNAUTHORIZED)

    folder_path = request.POST.get('folder_path', None)
    if folder_path is None:
        return HttpResponse('Bad request - folder_path is not included',
                            status=status.HTTP_400_BAD_REQUEST)
    folder_path = str(folder_path).strip()
    if not folder_path:
        return HttpResponse('Bad request - folder_path cannot be empty',
                            status=status.HTTP_400_BAD_REQUEST)

    if not folder_path.startswith('data/contents/'):
        return HttpResponse('Bad request - folder_path must start with data/contents/',
                            status=status.HTTP_400_BAD_REQUEST)

    if folder_path.find('/../') >= 0 or folder_path.endswith('/..'):
        return HttpResponse('Bad request - folder_path must not contain /../',
                            status=status.HTTP_400_BAD_REQUEST)

    try:
        create_folder(res_id, folder_path)
    except SessionException as ex:
        return HttpResponse(ex.stderr, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except DRF_ValidationError as ex:
        return HttpResponse(ex.detail, status=status.HTTP_400_BAD_REQUEST)

    return_object = {'new_folder_rel_path': folder_path}

    return HttpResponse(
        json.dumps(return_object),
        content_type="application/json"
    )


def data_store_remove_folder(request):
    """
    remove a sub-folder/sub-collection in hydroshareZone or any federated zone used for HydroShare
    resource backend store. It is invoked by an AJAX call and returns json object that include a
    status of 'success' if succeeds, and HttpResponse of status code of 403, 400, or 500 if fails.
    The AJAX request must be a POST request with input data passed in for res_id and folder_path
    where folder_path is the relative path for the folder to be removed under
    res_id collection/directory.
    """
    res_id = request.POST.get('res_id', None)
    if res_id is None:
        return HttpResponse('Bad request - resource id is not included',
                            status=status.HTTP_400_BAD_REQUEST)
    res_id = str(res_id).strip()
    try:
        resource, _, user = authorize(request, res_id,
                                      needed_permission=ACTION_TO_AUTHORIZE.EDIT_RESOURCE)
    except NotFound:
        return HttpResponse('Bad request - resource not found', status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied:
        return HttpResponse('Permission denied', status=status.HTTP_401_UNAUTHORIZED)

    folder_path = request.POST.get('folder_path', None)
    if folder_path is None:
        return HttpResponse('Bad request - folder_path is not included',
                            status=status.HTTP_400_BAD_REQUEST)
    folder_path = str(folder_path).strip()
    if not folder_path:
        return HttpResponse('Bad request - folder_path cannot be empty',
                            status=status.HTTP_400_BAD_REQUEST)

    if not folder_path.startswith('data/contents/'):
        return HttpResponse('Bad request - folder_path must start with data/contents/',
                            status=status.HTTP_400_BAD_REQUEST)

    if folder_path.find('/../') >= 0 or folder_path.endswith('/..'):
        return HttpResponse('Bad request - folder_path must not contain /../',
                            status=status.HTTP_400_BAD_REQUEST)

    try:
        remove_folder(user, res_id, folder_path)
    except SessionException as ex:
        return HttpResponse(ex.stderr, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as ex:
        return HttpResponse(ex.message, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return_object = {'status': 'success'}
    return HttpResponse(
        json.dumps(return_object),
        content_type="application/json"
    )


def data_store_file_or_folder_move_or_rename(request, res_id=None):
    """
    Move or rename a file or folder in hydroshareZone or any federated zone used for HydroShare
    resource backend store. It is invoked by an AJAX call and returns json object that has the
    relative path of the target file or folder being moved to if succeeds, and return empty string
    if fails. The AJAX request must be a POST request with input data passed in for res_id,
    source_path, and target_path where source_path and target_path are the relative paths for the
    source and target file or folder under res_id collection/directory.
    """
    res_id = request.POST.get('res_id', res_id)
    if res_id is None:
        return HttpResponse('Bad request - resource id is not included',
                            status=status.HTTP_400_BAD_REQUEST)
    res_id = str(res_id).strip()
    try:
        resource, _, user = authorize(request, res_id,
                                      needed_permission=ACTION_TO_AUTHORIZE.EDIT_RESOURCE)
    except NotFound:
        return HttpResponse('Bad request - resource not found', status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied:
        return HttpResponse('Permission denied', status=status.HTTP_401_UNAUTHORIZED)

    src_path = resolve_request(request).get('source_path', None)
    tgt_path = resolve_request(request).get('target_path', None)
    if src_path is None or tgt_path is None:
        return HttpResponse('Bad request - src_path or tgt_path is not included',
                            status=status.HTTP_400_BAD_REQUEST)
    src_path = str(src_path).strip()
    tgt_path = str(tgt_path).strip()
    if not src_path or not tgt_path:
        return HttpResponse('Bad request - src_path or tgt_path cannot be empty',
                            status=status.HTTP_400_BAD_REQUEST)

    if not src_path.startswith('data/contents/'):
        return HttpResponse('Bad request - src_path must start with data/contents/',
                            status=status.HTTP_400_BAD_REQUEST)
    if src_path.find('/../') >= 0 or src_path.endswith('/..'):
        return HttpResponse('Bad request - src_path cannot contain /../',
                            status=status.HTTP_400_BAD_REQUEST)

    if not tgt_path.startswith('data/contents/'):
        return HttpResponse('Bad request - tgt_path must start with data/contents/',
                            status=status.HTTP_400_BAD_REQUEST)

    if tgt_path.find('/../') >= 0 or tgt_path.endswith('/..'):
        return HttpResponse('Bad request - tgt_path cannot contain /../',
                            status=status.HTTP_400_BAD_REQUEST)

    try:
        move_or_rename_file_or_folder(user, res_id, src_path, tgt_path)
    except SessionException as ex:
        return HttpResponse(ex.stderr, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except DRF_ValidationError as ex:
        return HttpResponse(ex.detail, status=status.HTTP_400_BAD_REQUEST)

    return_object = {'target_rel_path': tgt_path}

    return HttpResponse(
        json.dumps(return_object),
        content_type='application/json'
    )


@api_view(['POST'])
def data_store_file_or_folder_move_or_rename_public(request, pk):
    return data_store_file_or_folder_move_or_rename(request, res_id=pk)


@api_view(['POST'])
def data_store_move_to_folder(request, pk=None):
    """
    Move a list of files and/or folders to another folder in a resource file hierarchy.

    :param request: a REST request
    :param pk: the short_id of a resource to modify, from REST URL.

    It is invoked by an AJAX call and returns a json object that has the relative paths of
    the target files or folders to which files have been moved. The AJAX request must be a POST
    request with input data passed in for source_paths and target_path where source_paths
    and target_path are the relative paths for the source and target file or folder in the
    res_id file directory.

    This routine is **specifically** targeted at validating requests from the UI.
    Thus it is much more limiting than a general purpose REST responder.
    """
    pk = request.POST.get('res_id', pk)
    if pk is None:
        return HttpResponse('Bad request - resource id is not included',
                            status=status.HTTP_400_BAD_REQUEST)

    # whether to treat request as atomic: skip overwrites for valid request
    atomic = request.POST.get('atomic', 'false') == 'true'  # False by default

    pk = str(pk).strip()
    try:
        resource, _, user = authorize(request, pk,
                                      needed_permission=ACTION_TO_AUTHORIZE.EDIT_RESOURCE)
    except NotFound:
        return HttpResponse('Bad request - resource not found', status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied:
        return HttpResponse('Permission denied', status=status.HTTP_401_UNAUTHORIZED)

    tgt_path = resolve_request(request).get('target_path', None)
    src_paths = resolve_request(request).get('source_paths', None)
    if src_paths is None or tgt_path is None:
        return HttpResponse('Bad request - src_paths or tgt_path is not included',
                            status=status.HTTP_400_BAD_REQUEST)

    tgt_path = str(tgt_path).strip()
    if not tgt_path:
        return HttpResponse('Target directory not specified',
                            status=status.HTTP_400_BAD_REQUEST)

    # protect against common hacking attacks
    if not tgt_path.startswith('data/contents/'):
        return HttpResponse('Target directory path must start with data/contents/',
                            status=status.HTTP_400_BAD_REQUEST)
    if tgt_path.find('/../') >= 0 or tgt_path.endswith('/..'):
        return HttpResponse('Bad request - tgt_path cannot contain /../',
                            status=status.HTTP_400_BAD_REQUEST)

    istorage = resource.get_irods_storage()

    # strip trailing slashes (if any)
    tgt_path = tgt_path.rstrip('/')
    tgt_short_path = tgt_path[len('data/contents/'):]
    tgt_storage_path = os.path.join(resource.root_path, tgt_path)

    if not irods_path_is_directory(istorage, tgt_storage_path):
        return HttpResponse('Target of move is not an existing folder',
                            status=status.HTTP_400_BAD_REQUEST)

    src_paths = json.loads(src_paths)

    for i in range(len(src_paths)):
        src_paths[i] = str(src_paths[i]).strip().rstrip('/')

    # protect against common hacking attacks
    for src_path in src_paths:

        if not src_path.startswith('data/contents/'):
            return HttpResponse('Paths to be moved must start with data/contents/',
                                status=status.HTTP_400_BAD_REQUEST)

        if src_path.find('/../') >= 0 or src_path.endswith('/..'):
            return HttpResponse('Paths to be moved cannot contain /../',
                                status=status.HTTP_400_BAD_REQUEST)

    valid_src_paths = []
    skipped_tgt_paths = []

    for src_path in src_paths:
        src_storage_path = os.path.join(resource.root_path, src_path)
        src_short_path = src_path[len('data/contents/'):]

        # protect against stale data botches: source files should exist
        try:
            folder, file = ResourceFile.resource_path_is_acceptable(resource,
                                                                    src_storage_path,
                                                                    test_exists=True)
        except ValidationError:
            return HttpResponse('Source file {} does not exist'.format(src_short_path),
                                status=status.HTTP_400_BAD_REQUEST)

        if not irods_path_is_directory(istorage, src_storage_path):  # there is django record
            try:
                ResourceFile.get(resource, file, folder=folder)
            except ResourceFile.DoesNotExist:
                return HttpResponse('Source file {} does not exist'.format(src_short_path),
                                    status=status.HTTP_400_BAD_REQUEST)

        # protect against inadvertent overwrite
        base = os.path.basename(src_storage_path)
        tgt_overwrite = os.path.join(tgt_storage_path, base)
        if not istorage.exists(tgt_overwrite):
            valid_src_paths.append(src_path)  # partly qualified path for operation
        else:  # skip pre-existing objects
            skipped_tgt_paths.append(os.path.join(tgt_short_path, base))

    if skipped_tgt_paths:
        if atomic:
            message = 'move would overwrite {}'.format(', '.join(skipped_tgt_paths))
            return HttpResponse(message, status=status.HTTP_400_BAD_REQUEST)

    # if not atomic, then try to move the files that don't have conflicts
    # stop immediately on error.

    try:
        move_to_folder(user, pk, valid_src_paths, tgt_path)
    except SessionException as ex:
        return HttpResponse(ex.stderr, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except DRF_ValidationError as ex:
        return HttpResponse(ex.detail, status=status.HTTP_400_BAD_REQUEST)

    return_object = {'target_rel_path': tgt_path}

    if skipped_tgt_paths:  # add information on skipped steps
        message = '[Warn] skipped move to existing {}'.format(', '.join(skipped_tgt_paths))
        return_object['additional_status'] = message

    return HttpResponse(
        json.dumps(return_object),
        content_type='application/json'
    )


@api_view(['POST'])
def data_store_rename_file_or_folder(request, pk=None):
    """
    Rename one file or folder in a resource file hierarchy.  It is invoked by an AJAX call

    :param request: a REST request
    :param pk: the short_id of a resource to modify, from REST URL.

    This is invoked by an AJAX call in the UI. It returns a json object that has the
    relative path of the target file or folder that has been renamed. The AJAX request
    must be a POST request with input data for source_path and target_path, where source_path
    and target_path are the relative paths for the source and target file or folder.

    This routine is **specifically** targeted at validating requests from the UI.
    Thus it is much more limiting than a general purpose REST responder.
    """
    pk = request.POST.get('res_id', pk)
    if pk is None:
        return HttpResponse('Bad request - resource id is not included',
                            status=status.HTTP_400_BAD_REQUEST)
    pk = str(pk).strip()
    try:
        resource, _, user = authorize(request, pk,
                                      needed_permission=ACTION_TO_AUTHORIZE.EDIT_RESOURCE)
    except NotFound:
        return HttpResponse('Bad request - resource not found', status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied:
        return HttpResponse('Permission denied', status=status.HTTP_401_UNAUTHORIZED)

    src_path = resolve_request(request).get('source_path', None)
    tgt_path = resolve_request(request).get('target_path', None)
    if src_path is None or tgt_path is None:
        return HttpResponse('Source or target name is not specified',
                            status=status.HTTP_400_BAD_REQUEST)

    if not src_path or not tgt_path:
        return HttpResponse('Source or target name is empty',
                            status=status.HTTP_400_BAD_REQUEST)

    src_path = str(src_path).strip()
    tgt_path = str(tgt_path).strip()
    src_folder, src_base = os.path.split(src_path)
    tgt_folder, tgt_base = os.path.split(tgt_path)

    if src_folder != tgt_folder:
        return HttpResponse('Rename: Source and target names must be in same folder',
                            status=status.HTTP_400_BAD_REQUEST)

    if not src_path.startswith('data/contents/'):
        return HttpResponse('Rename: Source path must start with data/contents/',
                            status=status.HTTP_400_BAD_REQUEST)

    if src_path.find('/../') >= 0 or src_path.endswith('/..'):
        return HttpResponse('Rename: Source path cannot contain /../',
                            status=status.HTTP_400_BAD_REQUEST)

    if not tgt_path.startswith('data/contents/'):
        return HttpResponse('Rename: Target path must start with data/contents/',
                            status=status.HTTP_400_BAD_REQUEST)

    if tgt_path.find('/../') >= 0 or tgt_path.endswith('/..'):
        return HttpResponse('Rename: Target path cannot contain /../',
                            status=status.HTTP_400_BAD_REQUEST)

    istorage = resource.get_irods_storage()

    # protect against stale data botches: source files should exist
    src_storage_path = os.path.join(resource.root_path, src_path)
    try:
        folder, base = ResourceFile.resource_path_is_acceptable(resource,
                                                                src_storage_path,
                                                                test_exists=True)
    except ValidationError:
        return HttpResponse('Object to be renamed does not exist',
                            status=status.HTTP_400_BAD_REQUEST)

    if not irods_path_is_directory(istorage, src_storage_path):
        try:  # Django record should exist for each file
            ResourceFile.get(resource, base, folder=folder)
        except ResourceFile.DoesNotExist:
            return HttpResponse('Object to be renamed does not exist',
                                status=status.HTTP_400_BAD_REQUEST)

    # check that the target doesn't exist
    tgt_storage_path = os.path.join(resource.root_path, tgt_path)
    tgt_short_path = tgt_path[len('data/contents/'):]
    if istorage.exists(tgt_storage_path):
        return HttpResponse('Desired name is already in use',
                            status=status.HTTP_400_BAD_REQUEST)
    try:
        folder, base = ResourceFile.resource_path_is_acceptable(resource,
                                                                tgt_storage_path,
                                                                test_exists=False)
    except ValidationError:
        return HttpResponse('Poorly structured desired name {}'
                            .format(tgt_short_path),
                            status=status.HTTP_400_BAD_REQUEST)
    try:
        ResourceFile.get(resource, base, folder=tgt_short_path)
        return HttpResponse('Desired name {} is already in use'
                            .format(tgt_short_path),
                            status=status.HTTP_400_BAD_REQUEST)
    except ResourceFile.DoesNotExist:
        pass  # correct response

    try:
        rename_file_or_folder(user, pk, src_path, tgt_path)
    except SessionException as ex:
        return HttpResponse(ex.stderr, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except DRF_ValidationError as ex:
        return HttpResponse(ex.detail, status=status.HTTP_400_BAD_REQUEST)

    return_object = {'target_rel_path': tgt_path}

    return HttpResponse(
        json.dumps(return_object),
        content_type='application/json'
    )
